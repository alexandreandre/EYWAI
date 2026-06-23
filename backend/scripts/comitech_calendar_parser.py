"""Parse le calendrier Excel Quadra Comitech Composite → calendrier_prevu EYWAI."""

from __future__ import annotations

import calendar as cal_mod
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

import openpyxl

from scripts.comitech_calendar_data import (
    CALENDAR_DAILY_HOURS,
    CALENDAR_SOURCE,
    CALENDAR_YEAR,
    COMITECH_CALENDAR_SHEETS,
    CalendarSheetMapping,
    DEFAULT_XLSX,
)

SKIP_SHEETS = frozenset({"SOMMAIRE", "MODELE"})

MONTH_FR: dict[str, int] = {
    "JANVIER": 1,
    "FEVRIER": 2,
    "MARS": 3,
    "AVRIL": 4,
    "MAI": 5,
    "JUIN": 6,
    "JUILLET": 7,
    "AOUT": 8,
    "SEPTEMBRE": 9,
    "OCTOBRE": 10,
    "NOVEMBRE": 11,
    "DECEMBRE": 12,
}


def _normalize_text(value: str | None) -> str:
    folded = unicodedata.normalize("NFD", value or "")
    stripped = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.upper().strip())


def _sheet_key(name: str) -> str:
    return _normalize_text(name)


def _parse_month_header(value: object) -> int | None:
    if value is None:
        return None
    key = _normalize_text(str(value))
    return MONTH_FR.get(key)


def _is_holiday_label(label: str) -> bool:
    if not label:
        return False
    keywords = (
        "JOUR DE L'AN",
        "PAQUES",
        "PÂQUES",
        "FETE DU W",
        "FETE DU TRAVAIL",
        "ASCENSION",
        "PENTECOTE",
        "PENTECÔTE",
        "PENTE",
        "VICTOIRE",
        "NATIONALE",
        "ASSOMPTION",
        "TOUSSAINT",
        "ARMISTICE",
        "NOEL",
        "NOËL",
    )
    return any(k in label for k in keywords)


def _classify_absence_label(label: str) -> str:
    """Retourne un type EYWAI pour une mention H.Abs reconnue."""
    if _is_holiday_label(label):
        return "ferie"
    if any(k in label for k in ("MALADIE", "CARENCE", "ARRET", "ARRÊT", " AT ", "FIN CDI")):
        return "arret_maladie"
    if any(
        k in label
        for k in (
            "EVF",
            "DECES",
            "DÉCÈS",
            "PATERNIT",
            "MATERNIT",
            "NAISSANCE",
            "PACS",
        )
    ):
        return "conge"
    if any(k in label for k in ("RECUP", "RÉCUP", "REPOS", " HR")):
        return "conge"
    if "JC" in label or "JOUR CADRE" in label:
        return "conge"
    if "FORMATION" in label or label.startswith("SST"):
        return "travail"
    if label.startswith("VM"):
        return "travail"
    if label in ("", " "):
        return "conge"
    return "conge"


def _parse_cp_value(raw: object) -> float | str | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    upper = _normalize_text(text)
    if upper in ("JFNP", "PENTE", "PENTECOTE", "PENTECÔTE"):
        return upper
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return upper


def _day_entry(
    *,
    jour: int,
    day_type: str,
    heures: float | None,
    note: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "jour": jour,
        "type": day_type,
        "heures_prevues": heures,
    }
    if note and day_type == "arret_maladie":
        entry["arret_type"] = "maladie_simple"
    return entry


def classify_planned_day(
    day_date: date,
    hab_raw: object,
    cp_raw: object,
    *,
    daily_hours: float = CALENDAR_DAILY_HOURS,
) -> dict[str, Any]:
    """Convertit une ligne Excel (H.Abs / CP) en entrée calendrier_prevu."""
    jour = day_date.day
    if day_date.weekday() >= 5:
        return _day_entry(jour=jour, day_type="weekend", heures=0.0)

    cp = _parse_cp_value(cp_raw)
    hab_text = ""
    hab_is_blank_marker = False
    if hab_raw is not None and not isinstance(hab_raw, (int, float)):
        raw_str = str(hab_raw)
        if raw_str.strip() == "" and raw_str != "":
            hab_is_blank_marker = True
        else:
            hab_text = raw_str.strip()
    hab_norm = _normalize_text(hab_text)

    if isinstance(hab_raw, (int, float)) and float(hab_raw) < 0:
        return _day_entry(jour=jour, day_type="conge", heures=daily_hours)

    if hab_is_blank_marker:
        return _day_entry(jour=jour, day_type="conge", heures=daily_hours)

    if cp is not None:
        if isinstance(cp, str):
            if cp in ("JFNP", "PENTE", "PENTECOTE", "PENTECÔTE"):
                return _day_entry(jour=jour, day_type="ferie", heures=None)
        elif isinstance(cp, float):
            if cp <= 0:
                pass
            elif cp >= 1:
                return _day_entry(jour=jour, day_type="conge", heures=daily_hours)
            else:
                return _day_entry(
                    jour=jour,
                    day_type="conge",
                    heures=round(daily_hours * cp, 2),
                )

    if hab_text and hab_norm:
        if _is_holiday_label(hab_norm):
            return _day_entry(jour=jour, day_type="ferie", heures=None)
        day_type = _classify_absence_label(hab_norm)
        if day_type == "travail":
            return _day_entry(jour=jour, day_type="travail", heures=daily_hours)
        if day_type == "ferie":
            return _day_entry(jour=jour, day_type="ferie", heures=None)
        if day_type == "arret_maladie":
            return _day_entry(
                jour=jour,
                day_type="arret_maladie",
                heures=daily_hours,
                note=hab_text,
            )
        return _day_entry(jour=jour, day_type="conge", heures=daily_hours)

    return _day_entry(jour=jour, day_type="travail", heures=daily_hours)


def build_default_month_calendar(
    year: int,
    month: int,
    *,
    daily_hours: float = CALENDAR_DAILY_HOURS,
    holiday_days: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Semaine type 39 h + week-ends + fériés entreprise."""
    _, n_days = cal_mod.monthrange(year, month)
    holidays = holiday_days or set()
    entries: list[dict[str, Any]] = []
    for jour in range(1, n_days + 1):
        wd = date(year, month, jour).weekday()
        if wd >= 5:
            entries.append(_day_entry(jour=jour, day_type="weekend", heures=0.0))
        elif jour in holidays:
            entries.append(_day_entry(jour=jour, day_type="ferie", heures=None))
        else:
            entries.append(
                _day_entry(jour=jour, day_type="travail", heures=daily_hours)
            )
    return entries


def _parse_sheet_month_blocks(ws) -> list[tuple[int, int]]:
    """Retourne [(month, base_col), ...] pour les blocs mensuels de la feuille."""
    blocks: list[tuple[int, int]] = []
    for col in range(1, ws.max_column + 1, 4):
        month = _parse_month_header(ws.cell(1, col).value)
        if month:
            blocks.append((month, col))
    return blocks


def parse_employee_sheet(ws, *, year: int = CALENDAR_YEAR) -> dict[int, list[dict[str, Any]]]:
    """Parse une feuille salarié → {mois: calendrier_prevu}."""
    by_month: dict[int, list[dict[str, Any]]] = {}
    for month, base_col in _parse_sheet_month_blocks(ws):
        entries: list[dict[str, Any]] = []
        for row in range(2, 33):
            day_raw = ws.cell(row, base_col + 1).value
            if day_raw is None:
                continue
            try:
                jour = int(day_raw)
            except (TypeError, ValueError):
                continue
            try:
                day_date = date(year, month, jour)
            except ValueError:
                continue
            hab = ws.cell(row, base_col + 2).value
            cp = ws.cell(row, base_col + 3).value
            entries.append(classify_planned_day(day_date, hab, cp))
        if entries:
            by_month[month] = sorted(entries, key=lambda e: e["jour"])
    return by_month


def load_workbook_sheets(xlsx_path: Path | None = None) -> dict[str, Any]:
    path = xlsx_path or DEFAULT_XLSX
    if not path.is_file():
        raise FileNotFoundError(f"Calendrier Excel introuvable : {path}")
    wb = openpyxl.load_workbook(path, data_only=True)
    sheets: dict[str, Any] = {}
    for name in wb.sheetnames:
        key = _sheet_key(name)
        if key in SKIP_SHEETS:
            continue
        sheets[key] = wb[name]
    return sheets


def sheet_mapping_by_key() -> dict[str, CalendarSheetMapping]:
    return {_sheet_key(m.sheet_key): m for m in COMITECH_CALENDAR_SHEETS}


def build_planned_calendar_payload(
    entries: list[dict[str, Any]],
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    return {
        "periode": {"mois": month, "annee": year},
        "source": CALENDAR_SOURCE,
        "calendrier_prevu": entries,
    }


__all__ = [
    "build_default_month_calendar",
    "build_planned_calendar_payload",
    "classify_planned_day",
    "load_workbook_sheets",
    "parse_employee_sheet",
    "sheet_mapping_by_key",
]
