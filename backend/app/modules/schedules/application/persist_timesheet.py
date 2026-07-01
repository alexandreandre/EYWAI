"""Persistance batch des propositions d'import pointages."""

from __future__ import annotations

import calendar as cal_mod
from typing import List

from app.modules.schedules.schemas.ai import DayNature
from app.modules.schedules.schemas.persist import (
    PersistTimesheetRequest,
    PersistTimesheetResponse,
    PersistTimesheetResult,
)


def _merge_days(existing: list, incoming: list, nature: DayNature) -> list:
    by_jour = {d.get("jour"): d for d in existing if d.get("jour")}
    for day in incoming:
        jour = day.jour
        if nature == "prevu":
            by_jour[jour] = {
                "jour": jour,
                "type": day.type,
                "heures_prevues": day.heures,
            }
        else:
            by_jour[jour] = {
                "jour": jour,
                "type": day.type,
                "heures_faites": day.heures,
            }
    return sorted(by_jour.values(), key=lambda x: x["jour"])


def persist_timesheet_batch(
    payload: PersistTimesheetRequest,
    *,
    get_planned,
    get_actual,
    update_planned,
    update_actual,
) -> PersistTimesheetResponse:
    """
    Merge serveur prevu/réel pour chaque employé.

    Les callables injectés permettent les tests unitaires sans DB.
    """
    results: List[PersistTimesheetResult] = []
    errors: List[dict] = []
    total_days = 0

    for emp in payload.employees:
        if not emp.employee_id or not emp.days:
            continue
        prevu_days = [d for d in emp.days if d.nature == "prevu"]
        reel_days = [d for d in emp.days if d.nature == "reel"]
        days_written = 0
        try:
            if prevu_days:
                existing = get_planned(emp.employee_id, payload.year, payload.month)
                merged = _merge_days(existing, prevu_days, "prevu")
                update_planned(emp.employee_id, payload.year, payload.month, merged)
                days_written += len(prevu_days)
            if reel_days:
                existing = get_actual(emp.employee_id, payload.year, payload.month)
                merged = _merge_days(existing, reel_days, "reel")
                update_actual(emp.employee_id, payload.year, payload.month, merged)
                days_written += len(reel_days)
            total_days += days_written
            results.append(
                PersistTimesheetResult(
                    employee_id=emp.employee_id,
                    days_written=days_written,
                    success=True,
                )
            )
        except Exception as exc:
            errors.append({"employee_id": emp.employee_id, "message": str(exc)})
            results.append(
                PersistTimesheetResult(
                    employee_id=emp.employee_id,
                    days_written=0,
                    success=False,
                    error=str(exc),
                )
            )

    return PersistTimesheetResponse(
        year=payload.year,
        month=payload.month,
        employees_processed=len(results),
        total_days_written=total_days,
        results=results,
        errors=errors,
    )


def validate_persist_payload(payload: PersistTimesheetRequest) -> None:
    default_days_in_month = cal_mod.monthrange(payload.year, payload.month)[1]
    for emp in payload.employees:
        for day in emp.days:
            eff_year = day.year or payload.year
            eff_month = day.month or payload.month
            days_in_month = (
                default_days_in_month
                if (eff_year, eff_month) == (payload.year, payload.month)
                else cal_mod.monthrange(eff_year, eff_month)[1]
            )
            if day.jour < 1 or day.jour > days_in_month:
                raise ValueError(
                    f"Jour {day.jour} hors limites pour {eff_month}/{eff_year}."
                )


def run_persist_timesheet_batch(
    payload: PersistTimesheetRequest,
    *,
    company_id: str | None = None,
    user_id: str | None = None,
) -> PersistTimesheetResponse:
    """Persistance batch via commands/queries schedules ou commit staging."""
    if payload.batch_id and company_id:
        from app.modules.schedules.application.timesheet_import.commit_service import (
            begin_commit_batch,
            commit_batch_bulk,
        )
        from app.modules.schedules.schemas.timesheet_import import (
            TimesheetImportCommitRequest,
        )

        commit_req = TimesheetImportCommitRequest(
            allow_partial=payload.allow_partial,
            recalculate_payroll=payload.recalculate_payroll,
            employee_ids=[e.employee_id for e in payload.employees] or None,
        )
        begin_commit_batch(
            payload.batch_id,
            company_id=company_id,
            request=commit_req,
        )
        result = commit_batch_bulk(
            payload.batch_id,
            company_id=company_id,
            request=commit_req,
            user_id=user_id,
        )
        return PersistTimesheetResponse(
            year=payload.year,
            month=payload.month,
            employees_processed=result["employees_processed"],
            total_days_written=result["total_days_written"],
            results=[
                PersistTimesheetResult(
                    employee_id=e["employee_id"],
                    days_written=0,
                    success=False,
                    error=e.get("message"),
                )
                for e in result.get("errors", [])
            ],
            errors=result.get("errors", []),
        )

    from app.modules.schedules.application import commands, queries
    from app.modules.schedules.schemas.requests import (
        ActualHoursEntry,
        ActualHoursRequest,
        PlannedCalendarEntry,
        PlannedCalendarRequest,
    )

    validate_persist_payload(payload)

    def get_planned(employee_id: str, year: int, month: int) -> list:
        data = queries.get_planned_calendar(employee_id, year, month)
        return data.get("calendrier_prevu") or []

    def get_actual(employee_id: str, year: int, month: int) -> list:
        data = queries.get_actual_hours(employee_id, year, month)
        return data.get("calendrier_reel") or []

    def update_planned(employee_id: str, year: int, month: int, rows: list) -> None:
        entries = [PlannedCalendarEntry(**r) for r in rows]
        commands.update_planned_calendar(
            employee_id,
            PlannedCalendarRequest(year=year, month=month, calendrier_prevu=entries),
        )

    def update_actual(employee_id: str, year: int, month: int, rows: list) -> None:
        entries = [ActualHoursEntry(**r) for r in rows]
        commands.update_actual_hours(
            employee_id,
            ActualHoursRequest(year=year, month=month, calendrier_reel=entries),
        )

    return persist_timesheet_batch(
        payload,
        get_planned=get_planned,
        get_actual=get_actual,
        update_planned=update_planned,
        update_actual=update_actual,
    )


def run_persist_with_bulk_commit(
    payload: PersistTimesheetRequest,
    *,
    company_id: str,
    user_id: str | None,
) -> PersistTimesheetResponse:
    """Commit via staging batch (crée batch éphémère si absent)."""
    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_from_persist_request,
    )

    result = commit_from_persist_request(
        payload,
        company_id=company_id,
        user_id=user_id,
        batch_id=payload.batch_id,
        recalculate_payroll=payload.recalculate_payroll,
    )
    return PersistTimesheetResponse(
        year=payload.year,
        month=payload.month,
        employees_processed=result["employees_processed"],
        total_days_written=result["total_days_written"],
        results=[],
        errors=result.get("errors", []),
    )


__all__ = ["persist_timesheet_batch", "run_persist_timesheet_batch", "run_persist_with_bulk_commit", "validate_persist_payload"]
