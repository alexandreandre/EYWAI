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
from app.modules.admin_import.infrastructure import repository as admin_repo
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


class CommitCancelled(Exception):
    """Levée quand l'utilisateur a demandé l'annulation du commit en cours."""


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

    file_hash = batch.get("file_hash")
    if file_hash:
        timesheet_import_repository.release_committed_file_hash_lock(
            company_id,
            str(file_hash),
            keep_batch_id=batch_id,
        )

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
    # Un même employé peut apparaître dans plusieurs entrées de la proposition
    # (ex: import multi-fichiers où il figure sur plusieurs relevés). On fusionne
    # ses jours par employee_id, sinon l'upsert Supabase reçoit deux fois la même
    # clé (employee_id, year, month) dans la même commande et échoue.
    by_employee_id: Dict[str, List[AiDayEntry]] = {}
    for emp in proposal.employees:
        if not emp.employee_id or not emp.days:
            continue
        if emp.review_status == "error":
            continue
        if allowed is not None and emp.employee_id not in allowed:
            continue
        by_employee_id.setdefault(emp.employee_id, []).extend(
            AiDayEntry(
                jour=d.jour,
                heures=d.heures,
                type=d.type,
                nature=d.nature,
                year=d.year,
                month=d.month,
            )
            for d in emp.days
        )
    return [
        PersistTimesheetEmployee(employee_id=employee_id, days=days)
        for employee_id, days in by_employee_id.items()
    ]


def _upsert_employees_for_month(
    *,
    company_id: str,
    year: int,
    month: int,
    employees: List[PersistTimesheetEmployee],
    existing_rows: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], int, List[Dict[str, str]], List[Dict[str, Any]]]:
    upsert_payloads: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, Any]] = []
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
                avertissements: List[Dict[str, Any]] = []
                merged_planned = _merge_days(
                    planned_existing, prevu_days, "prevu", warnings=avertissements
                )
                warnings.extend(
                    {"employee_id": emp.employee_id, **w} for w in avertissements
                )
                # Les jours refusés (absence validée préservée) ne comptent pas.
                days_written += len(prevu_days) - len(avertissements)
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

    return upsert_payloads, total_days, errors, warnings


def _upsert_employees_for_month_fast(
    *,
    company_id: str,
    year: int,
    month: int,
    employees: List[PersistTimesheetEmployee],
    existing_rows: Dict[str, Dict[str, Any]],
    employee_company_ids: Dict[str, str],
) -> tuple[List[Dict[str, Any]], int, List[Dict[str, str]], List[Dict[str, Any]]]:
    upsert_payloads: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, Any]] = []
    total_days = 0
    days_in_month = cal_mod.monthrange(year, month)[1]

    for emp in employees:
        try:
            company_id_emp = employee_company_ids.get(emp.employee_id)
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
                avertissements: List[Dict[str, Any]] = []
                merged_planned = _merge_days(
                    planned_existing, prevu_days, "prevu", warnings=avertissements
                )
                warnings.extend(
                    {"employee_id": emp.employee_id, **w} for w in avertissements
                )
                # Les jours refusés (absence validée préservée) ne comptent pas.
                days_written += len(prevu_days) - len(avertissements)
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

    return upsert_payloads, total_days, errors, warnings


def _employees_from_month_group(group: Dict[str, Any]) -> List[PersistTimesheetEmployee]:
    employees: List[PersistTimesheetEmployee] = []
    for emp in group.get("employees") or []:
        if not emp.get("employee_id"):
            continue
        if emp.get("review_status") == "error":
            continue
        days = emp.get("days") or []
        if not days:
            continue
        employees.append(
            PersistTimesheetEmployee(
                employee_id=str(emp["employee_id"]),
                days=[AiDayEntry(**day) for day in days],
            )
        )
    return employees


def _build_planning_employee_commit_plan(
    month_groups: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for group in month_groups:
        year, month = int(group["year"]), int(group["month"])
        for emp in group.get("employees") or []:
            employee_id = emp.get("employee_id")
            if not employee_id or emp.get("review_status") == "error":
                continue
            days = emp.get("days") or []
            if not days:
                continue
            label = str(emp.get("matched_name") or emp.get("raw_name") or employee_id).strip()
            row = by_id.get(str(employee_id))
            if not row:
                by_id[str(employee_id)] = {
                    "employee_id": str(employee_id),
                    "label": label,
                    "months": [(year, month, days)],
                }
                continue
            # Deux groupes différents (ex: semaines distinctes) peuvent porter sur le
            # même (year, month) pour cet employé : on fusionne plutôt que de dupliquer,
            # sinon l'upsert Supabase échoue (même clé employee_id/year/month deux fois
            # dans la même commande ON CONFLICT).
            existing_months = row["months"]
            for idx, (existing_year, existing_month, existing_days) in enumerate(existing_months):
                if existing_year == year and existing_month == month:
                    existing_months[idx] = (existing_year, existing_month, existing_days + days)
                    break
            else:
                existing_months.append((year, month, days))
            if label and (not row.get("label") or len(label) > len(str(row.get("label") or ""))):
                row["label"] = label
    return sorted(by_id.values(), key=lambda item: str(item["label"]).lower())


def _commit_failure_message(exc: Exception) -> str:
    raw = str(exc)
    if "schedule_import_batches_company_hash_committed_idx" in raw or (
        "23505" in raw and "file_hash" in raw
    ):
        return (
            "Ce fichier a déjà été enregistré pour cette entreprise. "
            "Réanalysez le fichier puis relancez l'enregistrement."
        )
    return raw or "Erreur commit import."


def _finalize_batch_as_committed(
    batch_id: str,
    *,
    company_id: str,
    file_hash: str | None,
    summary: Dict[str, Any],
    extra_summary_fields: Dict[str, Any],
) -> None:
    if file_hash:
        timesheet_import_repository.release_committed_file_hash_lock(
            company_id,
            file_hash,
            keep_batch_id=batch_id,
        )
    timesheet_import_repository.update_batch(
        batch_id,
        {
            "status": "committed",
            "completed_at": _now_iso(),
            "error_message": None,
            "summary_json": {**summary, **extra_summary_fields},
        },
    )


def _emit_planning_commit_progress(
    batch_id: str,
    summary: Dict[str, Any],
    *,
    done: int,
    total: int,
    label: str,
    phase: str = "employee",
    employee_id: str | None = None,
    employees_queue: List[str] | None = None,
    completed_labels: List[str] | None = None,
) -> Dict[str, Any]:
    percent = 100 if total == 0 else min(100, round(done / total * 100))
    progress: Dict[str, Any] = {
        "done": done,
        "total": total,
        "percent": percent,
        "phase": phase,
        "phase_label": "Enregistrement des calendriers prévus",
        "label": label,
        "employee_id": employee_id,
        "completed_labels": completed_labels or [],
    }
    if employees_queue is not None:
        progress["employees_queue"] = employees_queue
    summary = {**summary, "commit_progress": progress}
    timesheet_import_repository.update_batch(batch_id, {"summary_json": summary})
    return summary


def _commit_multi_month_batch(
    batch: Dict[str, Any],
    *,
    company_id: str,
    request: TimesheetImportCommitRequest,
    user_id: str | None = None,
) -> Dict[str, Any]:
    summary = batch.get("summary_json") or {}
    month_groups = summary.get("month_groups") or []
    batch_id = str(batch["id"])
    preview = batch.get("preview_json") or {}
    proposal = AiCalendarProposalResponse.model_validate(preview)

    unmatched = [
        emp.get("raw_name") or "?"
        for group in month_groups
        for emp in group.get("employees") or []
        if not emp.get("employee_id") and emp.get("review_status") not in ("empty",)
    ]
    if unmatched and not request.allow_partial:
        raise ScheduleAppError(
            "validation",
            f"{len(unmatched)} salarié(s) non rapproché(s) — corrigez ou activez allow_partial.",
            status_code=422,
        )

    upsert_payloads: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, Any]] = []
    total_days = 0
    recalc_targets: List[tuple[str, int, int]] = []

    employees_plan = _build_planning_employee_commit_plan(month_groups)
    if not employees_plan:
        raise ScheduleAppError(
            "validation",
            "Aucun salarié prêt à enregistrer dans ce batch.",
            status_code=400,
        )

    employee_meta = {
        str(emp["id"]): emp
        for emp in admin_repo.list_company_employees(company_id)
        if emp.get("id")
    }

    by_month: Dict[tuple[int, int], List[PersistTimesheetEmployee]] = {}
    rejected_unknown: List[str] = []

    for plan in employees_plan:
        employee_id = str(plan["employee_id"])
        if employee_id not in employee_meta:
            rejected_unknown.append(employee_id)
            errors.append(
                {
                    "employee_id": employee_id,
                    "message": "Employé hors entreprise active.",
                }
            )
            continue
        for year, month, days in plan["months"]:
            by_month.setdefault((int(year), int(month)), []).append(
                PersistTimesheetEmployee(
                    employee_id=employee_id,
                    days=[AiDayEntry(**day) for day in days],
                )
            )

    month_keys = sorted(by_month)
    month_queue = [f"{month:02d}/{year}" for year, month in month_keys]
    summary = _emit_planning_commit_progress(
        batch_id,
        summary,
        done=0,
        total=len(month_queue),
        label="Préparation de l'enregistrement…",
        phase="starting",
        employees_queue=month_queue,
        completed_labels=[],
    )

    processed_employee_ids: Set[str] = set()
    for month_index, (year, month) in enumerate(month_keys):
        if timesheet_import_repository.is_cancel_requested(batch_id):
            raise CommitCancelled(
                f"Annulation après {month_index} mois traité(s) sur {len(month_keys)}."
            )
        month_employees = by_month[(year, month)]
        employee_ids = [emp.employee_id for emp in month_employees]
        label = f"{month:02d}/{year}"
        summary = _emit_planning_commit_progress(
            batch_id,
            summary,
            done=month_index,
            total=len(month_queue),
            label=label,
            phase="employee",
            employees_queue=month_queue,
            completed_labels=month_queue[:month_index],
        )
        existing_rows = schedule_repository.list_schedules_for_employees(
            employee_ids, year, month
        )
        (
            payloads,
            days_written,
            group_errors,
            group_warnings,
        ) = _upsert_employees_for_month_fast(
            company_id=company_id,
            year=year,
            month=month,
            employees=month_employees,
            existing_rows=existing_rows,
            employee_company_ids={
                emp_id: str(meta.get("company_id") or "")
                for emp_id, meta in employee_meta.items()
            },
        )
        errors.extend(group_errors)
        warnings.extend(group_warnings)
        if payloads:
            schedule_repository.bulk_upsert_schedules(payloads)
            upsert_payloads.extend(payloads)
            recalc_targets.extend(
                (str(payload["employee_id"]), year, month) for payload in payloads
            )
            total_days += days_written
            for payload in payloads:
                processed_employee_ids.add(str(payload["employee_id"]))

        summary = _emit_planning_commit_progress(
            batch_id,
            summary,
            done=month_index + 1,
            total=len(month_queue),
            label=label,
            phase="employee",
            employees_queue=month_queue,
            completed_labels=month_queue[: month_index + 1],
        )

    if not upsert_payloads:
        plan_count = len(employees_plan)
        unknown_count = len(rejected_unknown)
        upsert_error_count = len(errors) - unknown_count
        logger.error(
            "Batch %s: aucun upsert produit — plan=%s, hors_entreprise=%s, erreurs_upsert=%s, "
            "company_id=%s, employee_meta_size=%s, sample_unknown=%s, sample_meta_ids=%s",
            batch_id,
            plan_count,
            unknown_count,
            upsert_error_count,
            company_id,
            len(employee_meta),
            rejected_unknown[:5],
            list(employee_meta.keys())[:5],
        )
        if plan_count and unknown_count == plan_count:
            raise ScheduleAppError(
                "validation",
                (
                    f"Aucun des {plan_count} salarié(s) du batch n'appartient à l'entreprise "
                    f"active ({company_id}). Vérifiez que l'entreprise sélectionnée correspond "
                    "bien à l'import."
                ),
                status_code=400,
            )
        raise ScheduleAppError(
            "validation",
            (
                f"Aucun salarié prêt à enregistrer (plan={plan_count}, "
                f"hors entreprise={unknown_count}, erreurs upsert={upsert_error_count})."
            ),
            status_code=400,
        )

    if request.recalculate_payroll:
        from app.modules.schedules.application.commands import calculate_payroll_events

        for employee_id, year, month in recalc_targets:
            try:
                calculate_payroll_events(employee_id, year, month)
            except Exception as exc:
                logger.warning("Recalc paie %s: %s", employee_id, exc)

    _finalize_batch_as_committed(
        batch_id,
        company_id=company_id,
        file_hash=batch.get("file_hash"),
        summary=summary,
        extra_summary_fields={
            "committed_days": total_days,
            "employees_processed": len({p["employee_id"] for p in upsert_payloads}),
            "months_committed": len(month_groups),
            "commit_errors": errors,
            "commit_warnings": warnings,
            "commit_progress": {
                "phase": "completed",
                "employees_done": len({p["employee_id"] for p in upsert_payloads}),
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
        "employees_processed": len({p["employee_id"] for p in upsert_payloads}),
        "total_days_written": total_days,
        "errors": errors,
        "warnings": warnings,
    }


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

    summary = batch.get("summary_json") or {}
    if summary.get("multi_month") and summary.get("month_groups"):
        return _commit_multi_month_batch(
            batch,
            company_id=company_id,
            request=request,
            user_id=user_id,
        )

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

    upsert_payloads, total_days, errors, warnings = _upsert_employees_for_month(
        company_id=company_id,
        year=year,
        month=month,
        employees=employees,
        existing_rows=existing_rows,
    )

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
    _finalize_batch_as_committed(
        batch_id,
        company_id=company_id,
        file_hash=batch.get("file_hash"),
        summary=summary,
        extra_summary_fields={
            "committed_days": total_days,
            "employees_processed": len(upsert_payloads),
            "commit_errors": errors,
            "commit_warnings": warnings,
            "commit_progress": {
                "phase": "completed",
                "employees_done": len(upsert_payloads),
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
        "warnings": warnings,
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
    except CommitCancelled as exc:
        logger.info("Commit batch %s annulé par l'utilisateur: %s", batch_id, exc)
        try:
            batch = timesheet_import_repository.get_batch(batch_id) or {}
            summary = batch.get("summary_json") or {}
            previous_progress = summary.get("commit_progress") or {}
            summary.pop("cancel_requested", None)
            timesheet_import_repository.update_batch(
                batch_id,
                {
                    "status": "cancelled",
                    "completed_at": _now_iso(),
                    "error_message": "Import annulé par l'utilisateur.",
                    "summary_json": {
                        **summary,
                        "commit_progress": {
                            **previous_progress,
                            "phase": "cancelled",
                            "phase_label": "Import annulé",
                            "label": str(exc) or "Annulé",
                        },
                    },
                },
            )
        except Exception:
            logger.exception(
                "Echec persistance statut 'cancelled' pour batch %s", batch_id
            )
    except Exception as exc:
        logger.exception("Commit batch %s échoué", batch_id)
        try:
            batch = timesheet_import_repository.get_batch(batch_id) or {}
            summary = batch.get("summary_json") or {}
            timesheet_import_repository.update_batch(
                batch_id,
                {
                    "status": "failed",
                    "error_message": _commit_failure_message(exc),
                    "completed_at": _now_iso(),
                    "summary_json": {
                        **summary,
                        "commit_progress": {
                            "phase": "failed",
                            "error": _commit_failure_message(exc),
                        },
                    },
                },
            )
        except Exception:
            logger.exception(
                "Echec persistance statut 'failed' pour batch %s", batch_id
            )


def _month_groups_from_persist_payload(
    payload: PersistTimesheetRequest,
) -> List[Dict[str, Any]] | None:
    """Regroupe les jours du payload par (year, month) réel quand certains
    jours portent un mois différent de celui de la requête (semaine
    hebdomadaire à cheval sur deux mois, ancrée via `week_anchor_date` à
    l'extraction). Retourne None si tous les jours sont dans le mois de la
    requête, pour laisser le chemin mono-mois existant inchangé.
    """
    has_override = any(
        (d.year is not None and d.year != payload.year)
        or (d.month is not None and d.month != payload.month)
        for e in payload.employees
        for d in e.days
    )
    if not has_override:
        return None

    groups: Dict[tuple[int, int], Dict[str, Any]] = {}
    for emp in payload.employees:
        by_month: Dict[tuple[int, int], List[Dict[str, Any]]] = {}
        for d in emp.days:
            key = (d.year or payload.year, d.month or payload.month)
            by_month.setdefault(key, []).append(
                {
                    "jour": d.jour,
                    "heures": d.heures,
                    "type": d.type,
                    "nature": d.nature,
                }
            )
        for key, days in by_month.items():
            group = groups.setdefault(
                key, {"year": key[0], "month": key[1], "employees": []}
            )
            group["employees"].append(
                {
                    "employee_id": emp.employee_id,
                    "raw_name": emp.employee_id,
                    "days": days,
                }
            )
    return [groups[k] for k in sorted(groups)]


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
    month_groups = _month_groups_from_persist_payload(payload)
    extra_summary = (
        {
            "multi_month": True,
            "month_groups": month_groups,
            "months_count": len(month_groups),
        }
        if month_groups
        else None
    )
    batch = create_batch_from_proposal(
        company_id=company_id,
        user_id=user_id,
        proposal=proposal,
        source_type="nl_text",
        parser_key="manual",
        extra_summary=extra_summary,
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
