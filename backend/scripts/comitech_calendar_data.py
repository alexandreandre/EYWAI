"""Calendrier prévu 2026 Comitech Composite — source Excel RH Quadra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


# Clés normalisées (upper, strip) — une feuille par salarié planifié individuellement.
COMITECH_CALENDAR_SHEETS: tuple[CalendarSheetMapping, ...] = (
    CalendarSheetMapping("BOUFRIDA", "BOUFRIDA", "Samir"),
    CalendarSheetMapping("BOUVEYRON", "BOUVEYRON", "Michel", ("BOUVERYON",)),
    CalendarSheetMapping(
        "CASANOVA",
        "CASANOVA",
        "Vitor",
        ("CASANOVA DA SILVA",),
    ),
    CalendarSheetMapping("CHAMBERT", "CHAMBERT", "Lucas"),
    CalendarSheetMapping(
        "DA SILVA CARDOSO",
        "DA SILVA CARDOSO",
        "Vitor",
        ("DA SILVA", "CASANOVA DA SILVA"),
    ),
    CalendarSheetMapping(
        "EL IDRISSI",
        "MARCHICH",
        "Hafida",
        ("EL IDRISSI",),
    ),
    CalendarSheetMapping("GARCIA", "GARCIA", "Mickael"),
    CalendarSheetMapping("GENAND", "GENAND", "Catherine"),
    CalendarSheetMapping("GOYAT", "GOYAT", "Stephane"),
    CalendarSheetMapping(
        "GROS",
        "PRONIER",
        "Nadine",
        ("GROS",),
    ),
    CalendarSheetMapping("JEAN", "JEAN", "David"),
    CalendarSheetMapping("LACAQUE", "LACAQUE", "Virginie"),
    CalendarSheetMapping("LEBRUN", "LEBRUN", "Theo"),
    CalendarSheetMapping(
        "OUASSIF",
        "MARCHICH",
        "Yamena",
        ("OUASSIF",),
    ),
    CalendarSheetMapping("POINSIGNON", "POINSIGNON", "Thibault"),
    CalendarSheetMapping("SARDA", "SARDA", "Dominique"),
    CalendarSheetMapping("SOW", "SOW", "Mamadou"),
    CalendarSheetMapping("TROUILLOUD", "TROUILLOUD", "Florian"),
    CalendarSheetMapping("VALLAT", "VALLAT", "Romain"),
)
