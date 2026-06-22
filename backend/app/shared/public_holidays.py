"""Jours fériés observés — façade partagée (schedules, absences, front)."""

from __future__ import annotations

from datetime import date

from app.core.database import supabase
from app.modules.absences.domain.rtt_forfait import french_public_holiday_dates
from app.modules.companies.domain.public_holidays import normalize_observed_holiday_ids


def load_observed_holiday_ids(company_id: str | None) -> list[str] | None:
    if not company_id:
        return None
    resp = (
        supabase.table("companies")
        .select("settings")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    settings = rows[0].get("settings") or {}
    if not isinstance(settings, dict):
        return None
    ph = settings.get("public_holidays") or {}
    if not isinstance(ph, dict):
        return None
    raw = ph.get("observed_holiday_ids")
    if raw is None:
        return None
    return normalize_observed_holiday_ids(list(raw) if isinstance(raw, list) else None)


def observed_holiday_dates_for_month(
    year: int,
    month: int,
    company_id: str | None,
) -> set[date]:
    ids = load_observed_holiday_ids(company_id)
    holidays = french_public_holiday_dates(year, ids)
    return {d for d in holidays if d.month == month and d.year == year}


def day_numbers_observed_holidays(
    year: int,
    month: int,
    company_id: str | None,
) -> set[int]:
    return {d.day for d in observed_holiday_dates_for_month(year, month, company_id)}


__all__ = [
    "day_numbers_observed_holidays",
    "load_observed_holiday_ids",
    "observed_holiday_dates_for_month",
]
