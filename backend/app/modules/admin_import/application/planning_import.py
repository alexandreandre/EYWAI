"""Wrapper Super Admin pour l'import planning / calendrier prévu."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from app.modules.admin_import.infrastructure import repository as repo
from app.modules.admin_import.application.planning_import_summary import (
    build_planning_import_summary,
)
from app.modules.schedules.application.planning_import.service import (
    parse_planning_calendar_file,
)
from app.modules.schedules.application.timesheet_import.tabular_period import ImportPeriodConfig
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import RosterEmployee

PeriodImportMode = Literal["auto", "month", "year", "range"]


def parse_planning_import(
    content: bytes,
    filename: str,
    company_id: str,
    year: int,
    month: int | None = None,
    *,
    period_mode: PeriodImportMode = "month",
    start_year: int | None = None,
    start_month: int | None = None,
    end_year: int | None = None,
    end_month: int | None = None,
    column_mapping: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    _ = column_mapping
    company = repo.find_company(company_id)
    if not company:
        raise LookupError("Entreprise introuvable.")

    if period_mode == "month" and month is None:
        raise ValueError("Le mois est requis pour un import mensuel.")
    if period_mode == "range" and (
        start_year is None or start_month is None or end_year is None or end_month is None
    ):
        raise ValueError("La plage de dates est incomplète.")

    effective_month = month if month is not None else (start_month or 1)
    period_config = ImportPeriodConfig(
        mode=period_mode,
        year=year,
        month=effective_month,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    employees = repo.list_company_employees(company_id)
    roster = [
        RosterEmployee(
            id=str(e["id"]),
            first_name=str(e.get("first_name") or ""),
            last_name=str(e.get("last_name") or ""),
            time_tracking_id=e.get("time_tracking_id"),
        )
        for e in employees
    ]

    result = parse_planning_calendar_file(
        company_id=company_id,
        user_id=user_id,
        content=content,
        filename=filename,
        year=year,
        month=effective_month,
        roster=roster,
        period_config=period_config,
    )
    payload = result.model_dump(mode="json")
    preview = payload.get("preview")
    if hasattr(preview, "model_dump"):
        payload["preview"] = preview.model_dump(mode="json")
    batch = timesheet_import_repository.get_batch(
        str(payload.get("batch_id") or ""),
        company_id=company_id,
    )
    batch_summary = (batch or {}).get("summary_json") or {}
    batch_summary["period_mode"] = period_mode
    summary = build_planning_import_summary(
        preview=payload.get("preview"),
        batch_summary=batch_summary,
        parser_key=payload.get("parser_key"),
        period_mode=period_mode,
        year=year,
        month=effective_month,
    )
    roster_payload = [
        {
            "id": str(e["id"]),
            "first_name": str(e.get("first_name") or ""),
            "last_name": str(e.get("last_name") or ""),
            "time_tracking_id": e.get("time_tracking_id"),
        }
        for e in employees
    ]
    return {
        "company_id": company_id,
        "company_name": company.get("company_name") or "Entreprise",
        "year": year,
        "month": effective_month,
        "period_mode": period_mode,
        "summary": summary,
        "roster": roster_payload,
        **payload,
    }


def begin_planning_import_commit(
    batch_id: str,
    company_id: str,
    *,
    user_id: str | None = None,
) -> Dict[str, Any]:
    """Démarre l'enregistrement en arrière-plan (suivi via GET /planning/batches/{id})."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        begin_commit_batch,
    )
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

    request = TimesheetImportCommitRequest(allow_partial=True)
    started = begin_commit_batch(
        batch_id,
        company_id=company_id,
        request=request,
    )
    return {
        "batch_id": batch_id,
        "status": "committing",
        "launch_background": started,
    }


def run_planning_import_commit(
    batch_id: str,
    company_id: str,
    *,
    user_id: str | None = None,
) -> None:
    from app.modules.schedules.application.timesheet_import.commit_service import (
        run_commit_batch,
    )
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

    run_commit_batch(
        batch_id,
        company_id=company_id,
        request=TimesheetImportCommitRequest(allow_partial=True),
        user_id=user_id,
    )
