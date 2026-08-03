"""Lecture des congés payés saisis dans le calendrier de paie."""

from __future__ import annotations

from datetime import date

from app.core.database import supabase
from app.modules.absences.domain.planning_cp import extract_planning_cp_days
from app.modules.absences.infrastructure.pagination import fetch_all_rows


def list_planning_cp_days(employee_ids: list[str]) -> dict[str, list[str]]:
    """Jours de congés payés du planning, par salarié, en dates ISO."""
    if not employee_ids:
        return {}

    def page(offset: int, limit: int) -> list[dict]:
        resp = (
            supabase.table("employee_schedules")
            .select("employee_id, planned_calendar")
            .in_("employee_id", employee_ids)
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    days_by_employee: dict[str, list[str]] = {}
    for row in fetch_all_rows(page):
        days = extract_planning_cp_days(row.get("planned_calendar"))
        if days:
            days_by_employee.setdefault(str(row["employee_id"]), []).extend(days)
    return days_by_employee


def get_cp_opening_reference_dates(
    employee_ids: list[str],
) -> dict[str, date | None]:
    """
    Date de reprise des soldes par salarié.

    Les congés pris jusqu'à cette date sont déjà intégrés au solde d'ouverture.
    On retient la plus récente quand plusieurs années coexistent.
    """
    if not employee_ids:
        return {}

    def page(offset: int, limit: int) -> list[dict]:
        resp = (
            supabase.table("employee_leave_adjustments")
            .select("employee_id, cp_opening_reference_date")
            .in_("employee_id", employee_ids)
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    cutoffs: dict[str, date | None] = {}
    for row in fetch_all_rows(page):
        raw = row.get("cp_opening_reference_date")
        if not raw:
            continue
        try:
            parsed = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        eid = str(row["employee_id"])
        current = cutoffs.get(eid)
        if current is None or parsed > current:
            cutoffs[eid] = parsed
    return cutoffs
