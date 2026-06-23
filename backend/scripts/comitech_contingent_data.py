"""Paramètres contingent HS Comitech Composite (tableau Excel RH / Quadra)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

CONTINGENT_SETTINGS: dict[str, Any] = {
    "legal_cor_contingent_hours": 220.0,
    "management_contingent_hours": 360.0,
    "hours_per_rest_day": 7.0,
    "include_structural_hours": True,
    "pause_deduction_enabled": True,
    "pause_hs_deduction_per_workday": 0.058765,
    "workdays_per_year_for_pause": 260,
}

COMITECH_WEEKLY_HOURS = 39.0

CONTINGENT_VERIFY_YEAR = 2025
CONTINGENT_VERIFY_REFERENCE = date(2025, 12, 31)
CONTINGENT_RCR_SOURCE = "Registre contingent HS Comitech Composite — Excel 2025"


@dataclass(frozen=True)
class RcrAbsenceSeed2025:
    """RCR consommés en 2025 (heures prises) — reprise contingent au 31/12/2025."""

    last_name: str
    first_hint: str | None
    selected_days: tuple[date, ...]
    last_name_aliases: tuple[str, ...] = ()


def _weekdays_end_2025(count: int) -> tuple[date, ...]:
    """Jours ouvrés en fin d'année 2025 pour approximer les heures RCR."""
    days: list[date] = []
    cursor = date(2025, 12, 31)
    while len(days) < count and cursor.year == 2025:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor = date.fromordinal(cursor.toordinal() - 1)
    return tuple(reversed(days))


# GENAND : 56,75 h → 8 j × 7 h = 56 h (écart 0,75 h vs Excel)
COMITECH_RCR_ABSENCES_2025: tuple[RcrAbsenceSeed2025, ...] = (
    RcrAbsenceSeed2025(
        "GENAND",
        "Catherine",
        _weekdays_end_2025(8),
    ),
)

CONTINGENT_HS_SOURCE = "Registre contingent HS Comitech Composite — Excel 2025"
CONTINGENT_HS_PAYROLL_MONTH = 12


@dataclass(frozen=True)
class PaidHsSeed2025:
    """HS conjoncturelles payées cumulées au 31/12/2025 (registre Excel)."""

    last_name: str
    first_hint: str | None
    hours: float
    last_name_aliases: tuple[str, ...] = ()


# Heures payées au 31/12/2025 — reprise Excel Quadra (mois unique : décembre).
COMITECH_PAID_HS_2025: tuple[PaidHsSeed2025, ...] = (
    PaidHsSeed2025("GENAND", "Catherine", 62.50),
    PaidHsSeed2025("GOYAT", "Stephane", 45.20),
    PaidHsSeed2025("GROS", "Nadine", 113.25, last_name_aliases=("PRONIER",)),
    PaidHsSeed2025("JEAN", "David", 6.50),
    PaidHsSeed2025(
        "MARCHICH",
        "Yamena",
        144.00,
        last_name_aliases=("OUASSIF",),
    ),
    PaidHsSeed2025("POINSIGNON", "Thibault", 0.25),
    PaidHsSeed2025("TROUILLOUD", "Florian", 179.00),
    PaidHsSeed2025("VALLAT", "Romain", 52.00),
)
