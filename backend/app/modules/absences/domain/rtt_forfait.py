"""RTT forfait jours cadres — formule jours ouvrés travaillables − forfait annuel."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from app.modules.companies.domain.public_holidays import (
    DEFAULT_OBSERVED_HOLIDAY_IDS,
    normalize_observed_holiday_ids,
)

_HOLIDAY_DEFINITIONS: dict[str, dict[str, object]] = {
    "new_year": {"fixed": (1, 1)},
    "easter_monday": {"easter_offset": 1},
    "labor_day": {"fixed": (5, 1)},
    "victory_day": {"fixed": (5, 8)},
    "ascension": {"easter_offset": 39},
    "whit_monday": {"easter_offset": 50},
    "bastille_day": {"fixed": (7, 14)},
    "assumption": {"fixed": (8, 15)},
    "all_saints": {"fixed": (11, 1)},
    "armistice": {"fixed": (11, 11)},
    "christmas": {"fixed": (12, 25)},
}


def _easter_sunday(year: int) -> date:
    """Algorithme de Meeus/Jones/Butcher (calendrier grégorien)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def french_public_holiday_dates(
    year: int,
    observed_holiday_ids: Sequence[str] | None = None,
) -> list[date]:
    """Dates des jours fériés observés pour une année civile."""
    ids = normalize_observed_holiday_ids(
        list(observed_holiday_ids) if observed_holiday_ids else None
    )
    allowed = set(ids)
    easter = _easter_sunday(year)
    dates: list[date] = []

    for holiday_id in DEFAULT_OBSERVED_HOLIDAY_IDS:
        if holiday_id not in allowed:
            continue
        definition = _HOLIDAY_DEFINITIONS[holiday_id]
        fixed = definition.get("fixed")
        if fixed:
            month, day = fixed  # type: ignore[misc]
            dates.append(date(year, month, day))
            continue
        offset = definition.get("easter_offset")
        if offset is not None:
            dates.append(easter + timedelta(days=int(offset)))

    return dates


def count_weekdays_in_year(year: int) -> int:
    total = 0
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        if d.weekday() < 5:
            total += 1
        d += timedelta(days=1)
    return total


def count_weekday_public_holidays(
    year: int,
    observed_holiday_ids: Sequence[str] | None = None,
) -> int:
    """Jours fériés observés tombant un jour ouvré (lun–ven)."""
    count = 0
    for holiday in french_public_holiday_dates(year, observed_holiday_ids):
        if holiday.weekday() < 5:
            count += 1
    return count


def calculate_rtt_annual_forfait_jours(
    year: int,
    *,
    forfait_days: int = 214,
    cp_ouvres_deduction: float = 25.0,
    observed_holiday_ids: Sequence[str] | None = None,
) -> float:
    """
    RTT = jours ouvrés travaillables − forfait annuel.

    jours ouvrés travaillables = jours ouvrés annuels − CP ouvrés − fériés ouvrés.
    """
    weekdays = count_weekdays_in_year(year)
    holidays = count_weekday_public_holidays(year, observed_holiday_ids)
    workable = weekdays - float(cp_ouvres_deduction) - holidays
    rtt = workable - float(forfait_days)
    return round(max(0.0, rtt), 2)
