"""
Parseur Kelio / Bodet hebdomadaire (format simplifié).

Signature : « Kelio » ou « Bodet » + lignes matricule + dates DD/MM/YYYY + durées.
"""

from __future__ import annotations

import re
from typing import List

from app.modules.schedules.application.parsers.cegid_weekly import (
    CegidDayEntry,
    CegidEmployeeBlock,
    CegidParseResult,
)

_KELIO_SIGNATURE = re.compile(r"\b(kelio|bodet|timeware)\b", re.IGNORECASE)
_EMPLOYEE_LINE = re.compile(
    r"^\s*(\d{1,6})\s+([A-ZÀ-ÿ][A-Za-zÀ-ÿ\s'\-]+?)\s*$",
    re.MULTILINE,
)
_DATE_HOURS = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2})[:h.](\d{2})",
    re.IGNORECASE,
)


def is_kelio_weekly_format(text: str) -> bool:
    if not _KELIO_SIGNATURE.search(text):
        return False
    return bool(_DATE_HOURS.search(text))


def try_parse_kelio_weekly(
    text: str,
    *,
    target_year: int,
    target_month: int,
) -> CegidParseResult:
    result = CegidParseResult(format_detected=False, confidence=0.0)
    if not is_kelio_weekly_format(text):
        return result

    result.format_detected = True
    employees: List[CegidEmployeeBlock] = []
    headers = list(_EMPLOYEE_LINE.finditer(text))
    for i, match in enumerate(headers):
        start = match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block_text = text[start:end]
        matricule = match.group(1)
        raw_name = match.group(2).strip()
        days: List[CegidDayEntry] = []
        for dm in _DATE_HOURS.finditer(block_text):
            d, m, y = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if y != target_year or m != target_month:
                continue
            hours = round(int(dm.group(4)) + int(dm.group(5)) / 60.0, 2)
            days.append(CegidDayEntry(jour=d, month=m, year=y, heures=hours))
        if days:
            employees.append(
                CegidEmployeeBlock(
                    matricule=matricule,
                    raw_name=raw_name,
                    days=days,
                    days_expected_count=len(days),
                    days_parsed_count=len(days),
                )
            )

    result.employees = employees
    if employees:
        result.confidence = min(0.85, 0.5 + 0.1 * len(employees))
    else:
        result.parse_warnings.append("Format Kelio détecté mais aucun jour exploitable.")
    return result


__all__ = ["is_kelio_weekly_format", "try_parse_kelio_weekly"]
