"""Agrégation mensuelle des métriques paie issues du planning."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.planning.domain.shift_payroll_metrics import (
    compute_night_hours,
    compute_paid_break_hours,
)


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    import calendar

    _, last = calendar.monthrange(year, month)
    return date(year, month, 1).isoformat(), date(year, month, last).isoformat()


def aggregate_shift_payroll_metrics(
    employee_id: str,
    year: int,
    month: int,
    *,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Somme nuit / pause / postes panier pour un salarié sur un mois."""
    start, end = _month_bounds(year, month)
    query = (
        supabase.table("shifts")
        .select(
            "id, start_time, end_time, is_locked, transverse_category, "
            "shift_types(code, paid_break_minutes, night_windows, meal_allowance_eligible)"
        )
        .eq("employee_id", employee_id)
        .eq("is_locked", True)
        .is_("transverse_category", "null")
        .gte("shift_date", start)
        .lte("shift_date", end)
    )
    if company_id:
        query = query.eq("company_id", company_id)
    resp = query.execute()
    rows = resp.data or []

    night_hours = 0.0
    weighted_night = 0.0
    paid_break_hours = 0.0
    meal_eligible_shifts = 0
    shift_count_by_code: dict[str, int] = {}

    for row in rows:
        st = row.get("shift_types") if isinstance(row.get("shift_types"), dict) else {}
        code = str(st.get("code") or "UNKNOWN")
        shift_count_by_code[code] = shift_count_by_code.get(code, 0) + 1

        if st.get("meal_allowance_eligible", True):
            meal_eligible_shifts += 1

        break_min = st.get("paid_break_minutes")
        paid_break_hours += compute_paid_break_hours(
            int(break_min) if break_min is not None else None
        )

        windows = st.get("night_windows") or []
        if isinstance(windows, list) and windows:
            night = compute_night_hours(
                str(row.get("start_time") or "00:00"),
                str(row.get("end_time") or "00:00"),
                windows,
            )
            night_hours += night.hours
            weighted_night += night.weighted_rate_hours

    avg_night_rate = round(weighted_night / night_hours, 4) if night_hours > 0 else 0.0

    return {
        "night_hours": round(night_hours, 2),
        "night_weighted_rate_hours": round(weighted_night, 4),
        "night_majoration_rate": avg_night_rate,
        "paid_break_hours": round(paid_break_hours, 2),
        "meal_eligible_shifts": meal_eligible_shifts,
        "shift_count_by_code": shift_count_by_code,
    }


__all__ = ["aggregate_shift_payroll_metrics"]
