"""Règles lissage de paie modulation — domaine pur."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.rules import resolve_modulation_tier


def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def count_low_weeks_in_month(settings: ModulationSettings, year: int, month: int) -> int:
    if not settings.enabled:
        return 0
    _, last_day = calendar.monthrange(year, month)
    count = 0
    seen: set[tuple[int, int]] = set()
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        iso = d.isocalendar()[:2]
        if iso in seen:
            continue
        seen.add(iso)
        monday = _monday_of_week(d)
        if resolve_modulation_tier(monday, settings) == "low":
            count += 1
    return count


def compute_smoothing_gain_for_month(
    settings: ModulationSettings,
    year: int,
    month: int,
    hourly_rate: float,
) -> float:
    """
    Lissage : complément de salaire sur semaines basses (moyenne − semaine basse) × nb semaines basses.
    """
    if not settings.enabled or not settings.pay_smoothed:
        return 0.0
    avg = float(settings.average_weekly_hours)
    low = float(settings.weekly_low_hours)
    if avg <= low or hourly_rate <= 0:
        return 0.0
    low_weeks = count_low_weeks_in_month(settings, year, month)
    hours = low_weeks * (avg - low)
    return round(hours * hourly_rate, 2)
