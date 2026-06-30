"""
Parseur Cegid « Banque heures V1 » (format Cartol et filiales similaires).

Signature : BANQUE HEURES V1 + blocs matricule/nom + lignes journalières
Date E1 S1 E2 S2 … avec total pointé en heures décimales (virgule).
"""

from __future__ import annotations

import re
from datetime import date
from typing import List, Optional

from app.modules.schedules.application.employee_match import is_junk_employee_name
from app.modules.schedules.application.parsers.cegid_weekly import (
    CegidDayEntry,
    CegidEmployeeBlock,
    CegidParseResult,
)

_FORMAT_SIGNATURE = re.compile(r"BANQUE\s+HEURES\s+V\d", re.IGNORECASE)
_EMPLOYEE_HEADER = re.compile(
    r"^(\d{4,6})\s+(.+?)\s+Solde\s+HS\s+avant",
    re.MULTILINE | re.IGNORECASE,
)
_DAILY_LINE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4})\s+(.+)$", re.MULTILINE)
_TIME_TOKEN = re.compile(r"^(?:\d{2}:\d{2}|__:_)$")
_DECIMAL_HOURS = re.compile(r"^(\d{1,2}),(\d{2})$")
_WEEK_SUMMARY = re.compile(r"^(\d{1,2})/(\d{4})\s+[\d,]+", re.MULTILINE)


def is_banque_heures_format(text: str) -> bool:
    if not text or len(text) < 300:
        return False
    if not _FORMAT_SIGNATURE.search(text):
        return False
    return bool(_EMPLOYEE_HEADER.search(text) and _DAILY_LINE.search(text))


def _parse_french_decimal_hours(token: str) -> Optional[float]:
    match = _DECIMAL_HOURS.match(token.strip())
    if not match:
        return None
    hours = float(f"{match.group(1)}.{match.group(2)}")
    if 0 <= hours <= 24:
        return round(hours, 2)
    return None


def _extract_daily_hours(rest: str) -> Optional[float]:
    """Première valeur décimale (X,XX) après les créneaux horaires."""
    tokens = rest.split()
    time_tokens_seen = 0
    for token in tokens:
        if _TIME_TOKEN.match(token):
            time_tokens_seen += 1
            continue
        if time_tokens_seen >= 4:
            hours = _parse_french_decimal_hours(token)
            if hours is not None:
                return hours
    return None


def _split_employee_blocks(text: str) -> List[tuple[str, str, str]]:
    """Retourne [(matricule, raw_name, block_text), …]."""
    headers = list(_EMPLOYEE_HEADER.finditer(text))
    blocks: List[tuple[str, str, str]] = []
    for idx, match in enumerate(headers):
        start = match.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        matricule = match.group(1).strip()
        raw_name = " ".join(match.group(2).split())
        if is_junk_employee_name(raw_name):
            continue
        blocks.append((matricule, raw_name, text[start:end]))
    return blocks


def try_parse_banque_heures(
    text: str,
    *,
    target_year: int,
    target_month: int,
) -> CegidParseResult:
    result = CegidParseResult(format_detected=False, confidence=0.0)
    if not is_banque_heures_format(text):
        return result

    result.format_detected = True
    employees: List[CegidEmployeeBlock] = []
    period_dates: List[date] = []

    for matricule, raw_name, block in _split_employee_blocks(text):
        days: List[CegidDayEntry] = []
        seen: set[tuple[int, int, int]] = set()

        for line_match in _DAILY_LINE.finditer(block):
            d_str, rest = line_match.group(1), line_match.group(2)
            try:
                parts = d_str.split("/")
                day_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
            except (ValueError, IndexError):
                continue

            period_dates.append(day_date)
            if day_date.year != target_year or day_date.month != target_month:
                continue

            hours = _extract_daily_hours(rest)
            if hours is None:
                continue

            key = (day_date.year, day_date.month, day_date.day)
            if key in seen:
                continue
            seen.add(key)
            days.append(
                CegidDayEntry(
                    jour=day_date.day,
                    month=day_date.month,
                    year=day_date.year,
                    heures=hours,
                )
            )

        if not days:
            continue

        days.sort(key=lambda item: item.jour)
        employees.append(
            CegidEmployeeBlock(
                matricule=matricule,
                raw_name=raw_name,
                days=days,
                week_days=list(days),
                days_expected_count=len(days),
                days_parsed_count=len(days),
            )
        )

    result.employees = employees
    if period_dates:
        result.period_start = min(period_dates)
        result.period_end = max(period_dates)

    week_match = _WEEK_SUMMARY.search(text)
    if week_match:
        result.week_number = int(week_match.group(1))
        result.week_year = int(week_match.group(2))

    if not employees:
        result.confidence = 0.2
        result.parse_warnings.append(
            "Format Banque heures détecté mais aucun jour exploitable pour la période."
        )
        return result

    expected_headers = len(_EMPLOYEE_HEADER.findall(text))
    parse_ratio = len(employees) / expected_headers if expected_headers else 1.0
    if parse_ratio >= 0.85:
        result.confidence = 0.95
    elif parse_ratio >= 0.5:
        result.confidence = 0.75
    else:
        result.confidence = 0.5

    if expected_headers and len(employees) < expected_headers * 0.5:
        result.parse_warnings.append(
            f"{len(employees)}/{expected_headers} salariés parsés pour le mois cible."
        )

    return result


__all__ = ["is_banque_heures_format", "try_parse_banque_heures"]
