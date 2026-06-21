"""Lecture absences pour variables paie."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase


def list_validated_absences_for_employees_in_range(
    employee_ids: list[str],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    if not employee_ids:
        return []
    resp = (
        supabase.table("absence_requests")
        .select("employee_id, type, status, workflow_step, selected_days")
        .in_("employee_id", employee_ids)
        .eq("status", "validated")
        .execute()
    )
    rows = resp.data or []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        days = row.get("selected_days") or []
        for raw in days:
            try:
                d = date.fromisoformat(str(raw)[:10])
            except (TypeError, ValueError):
                continue
            if start <= d <= end:
                filtered.append(row)
                break
    return filtered


def list_locked_shift_dates_for_employee(
    employee_id: str,
    start: date,
    end: date,
    *,
    company_id: str | None = None,
) -> list[date]:
    query = (
        supabase.table("shifts")
        .select("shift_date")
        .eq("employee_id", employee_id)
        .eq("is_locked", True)
        .is_("transverse_category", "null")
        .gte("shift_date", start.isoformat())
        .lte("shift_date", end.isoformat())
    )
    if company_id:
        query = query.eq("company_id", company_id)
    resp = query.execute()
    dates: list[date] = []
    for row in resp.data or []:
        raw = row.get("shift_date")
        if not raw:
            continue
        try:
            dates.append(date.fromisoformat(str(raw)[:10]))
        except (TypeError, ValueError):
            continue
    return dates
