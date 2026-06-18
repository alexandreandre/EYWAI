"""Intégration modulation — calcul paie et compteurs salariés."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.rules import (
    compute_balance_hours,
    resolve_modulation_tier,
    theoretical_weekly_hours,
)
from app.modules.modulation.infrastructure import repository as repo


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_modulation_weekly_hours_map(
    settings: ModulationSettings,
    year: int,
) -> dict[tuple[int, int], float]:
    """Carte (année ISO, semaine ISO) → heures théoriques modulation."""
    if not settings.enabled:
        return {}
    out: dict[tuple[int, int], float] = {}
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        monday = _monday_of_week(d)
        iso = monday.isocalendar()
        key = (iso[0], iso[1])
        if key not in out:
            tier = resolve_modulation_tier(monday, settings)
            out[key] = theoretical_weekly_hours(tier, settings)
        d += timedelta(days=7)
    return out


def _sum_hours_from_actual(actual: dict[str, Any] | None) -> float:
    if not actual or not isinstance(actual, dict):
        return 0.0
    total = 0.0
    for day_data in actual.values():
        if isinstance(day_data, dict):
            total += float(day_data.get("heures_faites") or 0)
        elif isinstance(day_data, (int, float)):
            total += float(day_data)
    return round(total, 2)


def _theoretical_hours_for_year(settings: ModulationSettings, year: int) -> float:
    weekly_map = build_modulation_weekly_hours_map(settings, year)
    return round(sum(weekly_map.values()), 2)


def sync_employee_modulation_counter(
    company_id: str,
    employee_id: str,
    year: int,
    *,
    settings: ModulationSettings | None = None,
) -> None:
    """Met à jour le compteur annuel théorique / réalisé / solde."""
    settings = settings or repo.get_modulation_settings(company_id)
    if not settings.enabled:
        return

    resp = (
        supabase.table("employee_schedules")
        .select("month, actual_hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .execute()
    )
    actual_total = 0.0
    for row in resp.data or []:
        actual_total += _sum_hours_from_actual(row.get("actual_hours"))

    theoretical = _theoretical_hours_for_year(settings, year)
    balance = compute_balance_hours(theoretical, actual_total)
    repo.upsert_employee_counter(
        company_id,
        employee_id,
        year,
        theoretical,
        actual_total,
        balance,
    )


def week_config_from_template(day_configs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Convertit day_configs DB en WeekConfig apply-model."""
    day_keys = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    default_work = {"type": "travail", "hours": 8.0}
    default_weekend = {"type": "weekend", "hours": 0.0}
    week: dict[str, Any] = {k: dict(default_weekend) for k in day_keys}
    for i, k in enumerate(day_keys[:5]):
        week[k] = dict(default_work)
    for cfg in day_configs or []:
        day_num = int(cfg.get("day") or 0)
        if 1 <= day_num <= 7:
            key = day_keys[day_num - 1]
            hours = float(cfg.get("hours") or 0)
            day_type = str(cfg.get("type") or "travail")
            if day_type == "repos" or hours <= 0:
                week[key] = {"type": "weekend", "hours": 0.0}
            else:
                week[key] = {"type": "travail", "hours": hours}
    return week
