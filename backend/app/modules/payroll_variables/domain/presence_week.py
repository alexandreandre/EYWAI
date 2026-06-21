"""Prime hebdomadaire conditionnelle — semaines sans absence (domaine pur)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any


def _parse_day(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def iso_week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iso_week_mondays_in_month(year: int, month: int) -> list[date]:
    """Lundis ISO des semaines qui intersectent le mois calendaire."""
    _, last_day = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    monday = iso_week_monday(start)
    mondays: list[date] = []
    while monday <= end:
        week_end = monday + timedelta(days=6)
        if week_end >= start:
            mondays.append(monday)
        monday += timedelta(days=7)
    return mondays


def absence_days_from_requests(
    requests: list[dict[str, Any]],
    *,
    absence_types: list[str],
    workflow_steps: list[str] | None = None,
) -> set[date]:
    """Jours d'absence validées filtrés par type (et workflow_step optionnel)."""
    types_set = {str(t).lower() for t in absence_types}
    wf_set = (
        {str(s).lower() for s in workflow_steps}
        if workflow_steps
        else None
    )
    days: set[date] = set()
    for req in requests:
        if str(req.get("status") or "").lower() != "validated":
            continue
        req_type = str(req.get("type") or "").lower()
        if req_type not in types_set:
            continue
        if wf_set is not None:
            wf = str(req.get("workflow_step") or "").lower()
            if wf not in wf_set:
                continue
        for raw in req.get("selected_days") or []:
            parsed = _parse_day(raw)
            if parsed:
                days.add(parsed)
    return days


def week_has_disqualifying_absence(
    monday: date,
    absence_days: set[date],
) -> bool:
    week_end = monday + timedelta(days=6)
    for d in absence_days:
        if monday <= d <= week_end:
            return True
    return False


def count_locked_shifts_in_week(
    monday: date,
    shift_dates: list[date],
) -> int:
    week_end = monday + timedelta(days=6)
    return sum(1 for d in shift_dates if monday <= d <= week_end)


def evaluate_presence_weeks(
    *,
    year: int,
    month: int,
    absence_requests: list[dict[str, Any]],
    conditions: dict[str, Any] | None,
    locked_shift_dates: list[date] | None = None,
) -> dict[str, Any]:
    """
    Retourne quantity (semaines éligibles), amount_per_week, details.
    absence_types vide → 0 semaines (RH doit configurer explicitement).
    """
    c = dict(conditions or {})
    absence_types = c.get("absence_types")
    if not isinstance(absence_types, list) or len(absence_types) == 0:
        return {
            "quantity": 0.0,
            "amount_per_week": float(c.get("amount_per_week") or 0),
            "details": {"skip_reason": "absence_types_not_configured"},
        }

    amount_per_week = float(c.get("amount_per_week") or 0)
    workflow_steps = c.get("workflow_steps")
    wf_list = (
        [str(s) for s in workflow_steps]
        if isinstance(workflow_steps, list) and workflow_steps
        else None
    )
    min_shifts = int(c.get("min_locked_shifts_per_week") or 0)
    absence_days = absence_days_from_requests(
        absence_requests,
        absence_types=[str(t) for t in absence_types],
        workflow_steps=wf_list,
    )
    shift_dates = locked_shift_dates or []
    eligible = 0
    week_details: list[dict[str, Any]] = []
    for monday in iso_week_mondays_in_month(year, month):
        disqualified = week_has_disqualifying_absence(monday, absence_days)
        shift_count = count_locked_shifts_in_week(monday, shift_dates)
        if min_shifts > 0 and shift_count < min_shifts:
            week_details.append(
                {
                    "monday": monday.isoformat(),
                    "eligible": False,
                    "reason": "insufficient_shifts",
                    "shift_count": shift_count,
                }
            )
            continue
        if disqualified:
            week_details.append(
                {
                    "monday": monday.isoformat(),
                    "eligible": False,
                    "reason": "absence",
                }
            )
            continue
        eligible += 1
        week_details.append(
            {
                "monday": monday.isoformat(),
                "eligible": True,
                "shift_count": shift_count,
            }
        )
    return {
        "quantity": float(eligible),
        "amount_per_week": amount_per_week,
        "details": {"weeks": week_details},
    }


__all__ = [
    "evaluate_presence_weeks",
    "iso_week_mondays_in_month",
    "absence_days_from_requests",
]
