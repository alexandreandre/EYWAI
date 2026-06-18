"""Règles métier modulation — domaine pur."""

from __future__ import annotations

from datetime import date, timedelta

from app.modules.modulation.domain.entities import ModulationSettings, ModulationTier


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def resolve_modulation_tier(
    week_start: date,
    settings: ModulationSettings,
) -> ModulationTier:
    """Détermine high/low/neutral pour une semaine ISO."""
    if not settings.enabled:
        return "neutral"
    anchor = settings.cycle_start_week_iso or date(week_start.year, 1, 1)
    anchor_monday = _monday_of_week(anchor)
    week_monday = _monday_of_week(week_start)
    if week_monday < anchor_monday:
        return "neutral"
    delta_weeks = (week_monday - anchor_monday).days // 7
    cycle_len = max(1, settings.high_weeks_per_cycle + settings.low_weeks_per_cycle)
    pos = delta_weeks % cycle_len
    if pos < settings.high_weeks_per_cycle:
        return "high"
    return "low"


def theoretical_weekly_hours(
    tier: ModulationTier,
    settings: ModulationSettings,
) -> float:
    if tier == "high":
        return settings.weekly_high_hours
    if tier == "low":
        return settings.weekly_low_hours
    return settings.average_weekly_hours


def compute_balance_hours(
    theoretical_hours: float,
    actual_hours: float,
) -> float:
    return round(actual_hours - theoretical_hours, 2)


def hours_beyond_weekly_cap(
    actual_hours: float,
    settings: ModulationSettings,
) -> float:
    excess = actual_hours - settings.weekly_cap_hours
    return round(max(0.0, excess), 2)
