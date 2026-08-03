"""Calendrier prévu 2026 Comitech Composite — source Excel RH Quadra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.donnees_nominatives import charger_ou_vide

CALENDAR_YEAR = 2026
CALENDAR_SOURCE = "Calendrier Excel Comitech Composite 2026"
CALENDAR_DAILY_HOURS = 7.8  # 39 h / 5 j

DEFAULT_XLSX = (
    Path(__file__).resolve().parent / "data" / "calendrier_2026_comitech.xlsx"
)


@dataclass(frozen=True)
class CalendarSheetMapping:
    """Feuille Excel → résolution salarié (même logique que participation / SPST)."""

    sheet_key: str
    last_name: str
    first_hint: str | None = None
    last_name_aliases: tuple[str, ...] = ()


def _charger_onglets() -> tuple[CalendarSheetMapping, ...]:
    """Une feuille Excel par salarié planifié individuellement.

    Le mapping onglet -> identité est une donnée personnelle : il vit dans
    `data/comitech/referentiel/calendrier-onglets.json`, hors dépôt Git.
    """
    return tuple(
        CalendarSheetMapping(
            sheet_key=ligne["sheet_key"],
            last_name=ligne["last_name"],
            first_hint=ligne.get("first_hint"),
            last_name_aliases=tuple(ligne.get("last_name_aliases") or ()),
        )
        for ligne in charger_ou_vide("comitech", "calendrier-onglets")
    )


COMITECH_CALENDAR_SHEETS: tuple[CalendarSheetMapping, ...] = _charger_onglets()

