"""
Parseur Cegid « Pointages retenu » en tableau horizontal (jours en colonnes).

Format typique Colorplast : en-tête Du … au …, colonnes Lundi–Vendredi avec dates,
lignes matricule + nom + totaux journaliers (# H:MM ou H:MM) + total semaine.
"""

from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

from app.modules.schedules.application.employee_match import is_junk_employee_name
from app.modules.schedules.application.parsers.cegid_weekly import (
    CegidDayEntry,
    CegidEmployeeBlock,
    CegidParseResult,
    _hhmm_to_hours,
)

_FORMAT_SIGNATURE = re.compile(
    r"pointages?\s+[\"']?retenu",
    re.IGNORECASE,
)
_PERIOD_HEADER = re.compile(
    r"Du\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+au\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)
_DAY_COLUMN = re.compile(
    r"(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)"
    r"\s+(\d{1,2})/(\d{1,2})/(\d{2,4})",
    re.IGNORECASE,
)
_EMPLOYEE_ROW = re.compile(
    r"^(\d{1,5})\s+(.+?)\s+(\d{1,2}:\d{2}.+)$",
    re.MULTILINE,
)
_TIME_VALUE = re.compile(r"(?:#\s*)?(\d{1,2})[:.;](\d{2})")
_WEEK_TOTAL = re.compile(
    r"Total\s+pour\s+la\s+semaine\s+"
    r"(?:(\d{1,2})/(\d{4})\s*[:.]?\s*)?(\d{1,2})[:.](\d{2})",
    re.IGNORECASE,
)


def _normalize_year(y: int) -> int:
    return 2000 + y if y < 100 else y


def is_cegid_horizontal_format(text: str) -> bool:
    if not text or len(text) < 200:
        return False
    if not _FORMAT_SIGNATURE.search(text):
        return False
    if not _PERIOD_HEADER.search(text):
        return False
    day_cols = _DAY_COLUMN.findall(text)
    if len(day_cols) < 3:
        return False
    return bool(_EMPLOYEE_ROW.search(text))


def _extract_day_columns(text: str) -> List[Tuple[int, int, int]]:
    columns: List[Tuple[int, int, int]] = []
    seen: set[Tuple[int, int, int]] = set()
    period = _PERIOD_HEADER.search(text)
    default_year = int(period.group(3)) if period else 2026
    for d_str, m_str, y_str in _DAY_COLUMN.findall(text):
        y = _normalize_year(int(y_str)) if y_str else default_year
        key = (y, int(m_str), int(d_str))
        if key not in seen:
            seen.add(key)
            columns.append(key)
    return columns


def _parse_row_hours(rest: str, expected_days: int) -> List[Optional[float]]:
    """Extrait les totaux journaliers d'une ligne salarié."""
    values: List[Optional[float]] = []
    for match in _TIME_VALUE.finditer(rest):
        hours = _hhmm_to_hours(match.group(1), match.group(2))
        if 0 <= hours <= 16:
            values.append(hours)
    week_total = _WEEK_TOTAL.search(rest)
    if week_total:
        tail_start = week_total.start()
        values = [
            v
            for m in _TIME_VALUE.finditer(rest[:tail_start])
            for v in [_hhmm_to_hours(m.group(1), m.group(2))]
            if 0 <= v <= 16
        ]
    if expected_days and len(values) > expected_days:
        values = values[:expected_days]
    return values


def try_parse_cegid_horizontal(
    text: str,
    *,
    target_year: int,
    target_month: int,
) -> CegidParseResult:
    result = CegidParseResult(format_detected=False, confidence=0.0)
    if not is_cegid_horizontal_format(text):
        return result

    result.format_detected = True
    period = _PERIOD_HEADER.search(text)
    period_start: date | None = None
    period_end: date | None = None
    if period:
        try:
            period_start = date(
                int(period.group(3)),
                int(period.group(2)),
                int(period.group(1)),
            )
            period_end = date(
                int(period.group(6)),
                int(period.group(5)),
                int(period.group(4)),
            )
            result.period_start = period_start
            result.period_end = period_end
        except ValueError:
            pass

    day_columns = _extract_day_columns(text)
    if not day_columns:
        result.parse_warnings.append("Colonnes jours non détectées dans le tableau.")
        return result

    week_match = _WEEK_TOTAL.search(text)
    if week_match and week_match.group(1) and week_match.group(2):
        result.week_number = int(week_match.group(1))
        result.week_year = int(week_match.group(2))

    employees: List[CegidEmployeeBlock] = []
    for row_match in _EMPLOYEE_ROW.finditer(text):
        matricule = row_match.group(1).strip()
        raw_name = " ".join(row_match.group(2).split())
        if is_junk_employee_name(raw_name):
            continue
        rest = row_match.group(3)
        if not _TIME_VALUE.search(rest):
            continue

        daily_hours = _parse_row_hours(rest, len(day_columns))
        if not daily_hours:
            continue

        days: List[CegidDayEntry] = []
        for idx, (y, m, d) in enumerate(day_columns):
            if idx >= len(daily_hours) or daily_hours[idx] is None:
                continue
            if y != target_year or m != target_month:
                continue
            days.append(
                CegidDayEntry(jour=d, month=m, year=y, heures=daily_hours[idx])
            )

        weekly_total: Optional[float] = None
        if week_match:
            weekly_total = _hhmm_to_hours(week_match.group(3), week_match.group(4))

        if not days and weekly_total is None:
            continue

        employees.append(
            CegidEmployeeBlock(
                matricule=matricule,
                raw_name=raw_name,
                days=days,
                week_days=days,
                weekly_total_hours=weekly_total,
                days_expected_count=len(
                    [c for c in day_columns if c[0] == target_year and c[1] == target_month]
                ),
                days_parsed_count=len(days),
            )
        )

    result.employees = employees
    if not employees:
        result.confidence = 0.2
        result.parse_warnings.append(
            "Tableau Cegid horizontal détecté mais aucune ligne salarié exploitable."
        )
        return result

    week_totals = len(_WEEK_TOTAL.findall(text))
    ratio = len(employees) / week_totals if week_totals else min(1.0, len(employees) / 3)
    if ratio >= 0.7:
        result.confidence = 0.9
    elif ratio >= 0.4:
        result.confidence = 0.75
    else:
        result.confidence = 0.55

    return result


__all__ = ["is_cegid_horizontal_format", "try_parse_cegid_horizontal"]
