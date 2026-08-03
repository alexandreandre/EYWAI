"""Paramètres contingent HS Comitech Composite (tableau Excel RH / Quadra)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from scripts.donnees_nominatives import charger_ou_vide
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


def _charger_rcr() -> tuple[RcrAbsenceSeed2025, ...]:
    """RCR consommés en 2025, par salarié — table hors dépôt Git."""
    return tuple(
        RcrAbsenceSeed2025(
            last_name=ligne["last_name"],
            first_hint=ligne.get("first_hint"),
            selected_days=tuple(
                date.fromisoformat(j) for j in ligne.get("selected_days") or ()
            ),
            last_name_aliases=tuple(ligne.get("last_name_aliases") or ()),
        )
        for ligne in charger_ou_vide("comitech", "rcr-absences-2025")
    )


COMITECH_RCR_ABSENCES_2025: tuple[RcrAbsenceSeed2025, ...] = _charger_rcr()


CONTINGENT_HS_SOURCE = "Registre contingent HS Comitech Composite — Excel 2025"
CONTINGENT_HS_PAYROLL_MONTH = 12


@dataclass(frozen=True)
class PaidHsSeed2025:
    """HS conjoncturelles payées cumulées au 31/12/2025 (registre Excel)."""

    last_name: str
    first_hint: str | None
    hours: float
    last_name_aliases: tuple[str, ...] = ()


def _charger_hs_payees() -> tuple[PaidHsSeed2025, ...]:
    """HS conjoncturelles payées au 31/12/2025, par salarié — hors dépôt Git."""
    return tuple(
        PaidHsSeed2025(
            last_name=ligne["last_name"],
            first_hint=ligne.get("first_hint"),
            hours=ligne["hours"],
            last_name_aliases=tuple(ligne.get("last_name_aliases") or ()),
        )
        for ligne in charger_ou_vide("comitech", "hs-payees-2025")
    )


COMITECH_PAID_HS_2025: tuple[PaidHsSeed2025, ...] = _charger_hs_payees()

