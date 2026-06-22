"""Commit async batch import pointages (pattern DSN)."""

from __future__ import annotations

import calendar as cal_mod
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.persist_timesheet import _merge_days
from app.modules.schedules.application.schedule_import_audit import (
    record_schedule_import_run,
)
from app.modules.schedules.application.service import get_employee_company_and_statut
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, AiDayEntry
from app.modules.schedules.schemas.persist import (
    PersistTimesheetEmployee,
    PersistTimesheetRequest,
)
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_type_for_day(year: int, month: int, jour: int) -> str:
    from datetime import date

    wd = date(year, month, jour).weekday()
    return "weekend" if wd >= 5 else "travail"


def begin_commit_batch(
    batch_id: str,
    *,
    company_id: str,
    request: TimesheetImportCommitRequest,
) -> bool:
    batch = timesheet_import_repository.get_batch(batch_id, company_id=company_id)
    if not batch:
        raise ScheduleAppError("validation", "Batch introuvable.", status_code=404)
    status = batch.get("status")
    if status == "committed":
        raise ScheduleAppError("validation", "Ce batch a déjà été validé.", status_code=409)
    if status == "committing":
        return False

    summary = batch.get("summary_json") or {}
    timesheet_import_repository.update_batch(
        batch_id,
        {
            "status": "committing",
            "summary_json": {
                **summary,
                "commit_request": request.model_dump(),
                "commit_progress": {"phase": "starting", "employees_done": 0},
            },
        },
    )
    return True


def _employees_from_batch(
    batch: Dict[str, Any],
    *,
    filter_ids: Optional[List[str]] = None,
) -> List[PersistTimesheetEmployee]:
    preview = batch.get("preview_json") or {}
    proposal = AiCalendarProposalResponse.model_validate(preview)
    allowed: Optional[Set[str]] = set(filter_ids) if filter_ids else None
    employees: List[PersistTimesheetEmployee] = []
    for emp in proposal.employees:
        if not emp.employee_id or not emp.days:
            continue
        if emp.review_status == "error":
            continue
        if allowed is not None and emp.employee_id not in allowed:
            continue
        employees.append(
            PersistTimesheetEmployee(
                employee_id=emp.employee_id,
                days=[
                    AiDayEntry(
                        jour=d.jour,
                        heures=d.heures,
                        type=d.type,
                        nature=d.nature,
                    )
                    for d in emp.days
                ],
            )
        )
    return employees


def commit_batch_bulk(
    batch_id: str,
    *,
    company_id: str,
    request: TimesheetImportCommitRequest,
    user_id: str | None = None,
) -> Dict[str, Any]:
    batch = timesheet_import_repository.get_batch(batch_id, company_id=company_id)
    if not batch:
        raise ScheduleAppError("validation", "Batch introuvable.", status_code=404)

    preview = batch.get("preview_json") or {}
    proposal = AiCalendarProposalResponse.model_validate(preview)
    year, month = proposal.year, proposal.month
    employees = _employees_from_batch(batch, filter_ids=request.employee_ids)

    if not employees:
        raise ScheduleAppError(
            "validation",
            "Aucun salarié prêt à enregistrer dans ce batch.",
            status_code=400,
        )

    unmatched = [
        e.raw_name
        for e in proposal.employees
        if not e.employee_id and e.review_status not in ("empty",)
    ]
    if unmatched and not request.allow_partial:
        raise ScheduleAppError(
            "validation",
            f"{len(unmatched)} salarié(s) non rapproché(s) — corrigez ou activez allow_partial.",
            status_code=422,
        )

    employee_ids = [e.employee_id for e in employees]
    existing_rows = schedule_repository.list_schedules_for_employees(
        employee_ids, year, month
    )

    upsert_payloads: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    total_days = 0
    days_in_month = cal_mod.monthrange(year, month)[1]

    for emp in employees:
        try:
            company_id_emp, _ = get_employee_company_and_statut(emp.employee_id)
            if company_id_emp != company_id:
                errors.append(
                    {
                        "employee_id": emp.employee_id,
                        "message": "Employé hors entreprise active.",
                    }
                )
                continue

            row = existing_rows.get(emp.employee_id, {})
            prevu_days = [d for d in emp.days if d.nature == "prevu"]
            reel_days = [d for d in emp.days if d.nature == "reel"]

            planned_existing: list = []
            actual_existing: list = []
            if row:
                pc = row.get("planned_calendar") or {}
                ah = row.get("actual_hours") or {}
                planned_existing = pc.get("calendrier_prevu") or []
                actual_existing = ah.get("calendrier_reel") or []

            merged_planned = planned_existing
            merged_actual = actual_existing
            days_written = 0

            if prevu_days:
                merged_planned = _merge_days(planned_existing, prevu_days, "prevu")
                days_written += len(prevu_days)
            if reel_days:
                merged_actual = _merge_days(actual_existing, reel_days, "reel")
                days_written += len(reel_days)

            payload: Dict[str, Any] = {
                "employee_id": emp.employee_id,
                "company_id": company_id_emp,
                "year": year,
                "month": month,
            }
            if prevu_days:
                payload["planned_calendar"] = {
                    "periode": {"mois": month, "annee": year},
                    "calendrier_prevu": merged_planned,
                }
            if reel_days:
                payload["actual_hours"] = {
                    "periode": {"mois": month, "annee": year},
                    "calendrier_reel": merged_actual,
                }
            if not row and not prevu_days and reel_days:
                payload["planned_calendar"] = {
                    "periode": {"mois": month, "annee": year},
                    "calendrier_prevu": [
                        {
                            "jour": j,
                            "type": _default_type_for_day(year, month, j),
                            "heures_prevues": None,
                        }
                        for j in range(1, days_in_month + 1)
                    ],
                }

            upsert_payloads.append(payload)
            total_days += days_written
        except Exception as exc:
            errors.append({"employee_id": emp.employee_id, "message": str(exc)})

    if upsert_payloads:
        schedule_repository.bulk_upsert_schedules(upsert_payloads)

    if request.recalculate_payroll:
        from app.modules.schedules.application.commands import calculate_payroll_events

        for emp in employees:
            if emp.employee_id not in {p["employee_id"] for p in upsert_payloads}:
                continue
            try:
                calculate_payroll_events(emp.employee_id, year, month)
            except Exception as exc:
                logger.warning("Recalc paie %s: %s", emp.employee_id, exc)

    summary = batch.get("summary_json") or {}
    timesheet_import_repository.update_batch(
        batch_id,
        {
            "status": "committed",
            "completed_at": _now_iso(),
            "summary_json": {
                **summary,
                "committed_days": total_days,
                "employees_processed": len(upsert_payloads),
                "commit_errors": errors,
                "commit_progress": {
                    "phase": "completed",
                    "employees_done": len(upsert_payloads),
                },
            },
        },
    )

    try:
        record_schedule_import_run(
            company_id=company_id,
            user_id=user_id,
            filename=batch.get("filename") or "",
            proposal=proposal,
            import_job_id=batch.get("import_job_id"),
            batch_id=batch_id,
            extraction_mode=batch.get("parser_key"),
            days_written=total_days,
        )
    except Exception:
        logger.exception("Audit import run post-commit")

    return {
        "batch_id": batch_id,
        "status": "committed",
        "employees_processed": len(upsert_payloads),
        "total_days_written": total_days,
        "errors": errors,
    }


def run_commit_batch(
    batch_id: str,
    *,
    company_id: str,
    request: TimesheetImportCommitRequest,
    user_id: str | None = None,
) -> None:
    try:
        commit_batch_bulk(
            batch_id,
            company_id=company_id,
            request=request,
            user_id=user_id,
        )
    except Exception as exc:
        logger.exception("Commit batch %s échoué", batch_id)
        batch = timesheet_import_repository.get_batch(batch_id) or {}
        summary = batch.get("summary_json") or {}
        timesheet_import_repository.update_batch(
            batch_id,
            {
                "status": "failed",
                "error_message": str(exc) or "Erreur commit import.",
                "completed_at": _now_iso(),
                "summary_json": {
                    **summary,
                    "commit_progress": {"phase": "failed", "error": str(exc)},
                },
            },
        )


def commit_from_persist_request(
    payload: PersistTimesheetRequest,
    *,
    company_id: str,
    user_id: str | None,
    batch_id: str | None = None,
    recalculate_payroll: bool = False,
) -> Dict[str, Any]:
    """Chemin legacy persist-timesheet : crée batch éphémère ou commit direct."""
    if batch_id:
        return commit_batch_bulk(
            batch_id,
            company_id=company_id,
            request=TimesheetImportCommitRequest(
                recalculate_payroll=recalculate_payroll,
                employee_ids=[e.employee_id for e in payload.employees],
            ),
            user_id=user_id,
        )

    from app.modules.schedules.application.timesheet_import.batch_service import (
        create_batch_from_proposal,
    )
    from app.modules.schedules.schemas.ai import AiEmployeeProposal

    employees = [
        AiEmployeeProposal(
            raw_name=e.employee_id,
            employee_id=e.employee_id,
            days=e.days,
            review_status="ok",
            match_confidence="high",
            match_method="matricule",
        )
        for e in payload.employees
    ]
    proposal = AiCalendarProposalResponse(
        year=payload.year,
        month=payload.month,
        source="persist-direct",
        employees=employees,
    )
    batch = create_batch_from_proposal(
        company_id=company_id,
        user_id=user_id,
        proposal=proposal,
        source_type="nl_text",
        parser_key="manual",
    )
    return commit_batch_bulk(
        str(batch["id"]),
        company_id=company_id,
        request=TimesheetImportCommitRequest(recalculate_payroll=recalculate_payroll),
        user_id=user_id,
    )


__all__ = [
    "begin_commit_batch",
    "commit_batch_bulk",
    "commit_from_persist_request",
    "run_commit_batch",
]
