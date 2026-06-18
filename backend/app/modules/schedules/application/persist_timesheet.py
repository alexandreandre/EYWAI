"""Persistance batch des propositions d'import pointages."""

from __future__ import annotations

import calendar as cal_mod
from typing import List

from app.modules.schedules.schemas.ai import AiDayEntry, DayNature
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
    days_in_month = cal_mod.monthrange(payload.year, payload.month)[1]
    for emp in payload.employees:
        for day in emp.days:
            if day.jour < 1 or day.jour > days_in_month:
                raise ValueError(
                    f"Jour {day.jour} hors limites pour {payload.month}/{payload.year}."
                )


def run_persist_timesheet_batch(payload: PersistTimesheetRequest) -> PersistTimesheetResponse:
    """Persistance batch via commands/queries schedules."""
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


__all__ = ["persist_timesheet_batch", "run_persist_timesheet_batch", "validate_persist_payload"]
