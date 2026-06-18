"""
Parseur déterministe des relevés Cegid/GTA hebdomadaires « Pointages retenu ».

Format cible : en-tête Du DD/MM/YYYY au DD/MM/YYYY, blocs matricule + nom,
jours Lundi–Dimanche avec dates DD/MM/YY et total journalier après « # »,
total hebdomadaire « Total pour la semaine NN/YYYY: HH:MM ».
"""

from __future__ import annotations

import calendar as cal_mod
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from app.modules.schedules.application.employee_match import is_junk_employee_name

_FORMAT_SIGNATURE = re.compile(
    r"pointages?\s+[\"']?retenu|semaine\s+[àa]\s+semaine",
    re.IGNORECASE,
)
_PERIOD_HEADER = re.compile(
    r"Du\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+au\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)
_WEEK_TOTAL_RE = re.compile(
    r"Total\s+pour\s+la\s+semaine\s+"
    r"(?:(\d{1,2})/(\d{4})\s*[:.]?\s*)?(\d{1,2})[:.](\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_BLOCK_HEADER_RE = re.compile(
    r"^\s*(\d{1,5})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'\-]+?)(?:\s*$|\s+(?:Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\b)",
    re.MULTILINE | re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_DAY_MARKER_RE = re.compile(r"[#§nN]\s*(?:[^\d\n]{0,8})?(\d{1,2})[:.;](\d{2})")
_TIME_PAIR_RE = re.compile(r"\b(\d{1,2})[:.;](\d{2})\b")


@dataclass
class CegidDayEntry:
    jour: int
    month: int
    year: int
    heures: float


@dataclass
class CegidEmployeeBlock:
    matricule: str
    raw_name: str
    days: List[CegidDayEntry] = field(default_factory=list)
    week_days: List[CegidDayEntry] = field(default_factory=list)
    weekly_total_hours: Optional[float] = None
    weekly_total_label: Optional[str] = None
    empty_week: bool = False
    parse_warnings: List[str] = field(default_factory=list)
    days_expected_count: int = 0
    days_parsed_count: int = 0

    @property
    def coverage_ratio(self) -> float:
        if self.days_expected_count <= 0:
            return 1.0 if self.days_parsed_count > 0 else 0.0
        return round(self.days_parsed_count / self.days_expected_count, 3)


@dataclass
class CegidParseResult:
    format_detected: bool
    confidence: float
    week_number: Optional[int] = None
    week_year: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    employees: List[CegidEmployeeBlock] = field(default_factory=list)
    parse_warnings: List[str] = field(default_factory=list)

    @property
    def employee_count(self) -> int:
        return len(self.employees)


def _normalize_year(y: int) -> int:
    if y < 100:
        return 2000 + y
    return y


def _hhmm_to_hours(h: str, m: str) -> float:
    return round(int(h) + int(m) / 60.0, 2)


MAX_HOURS_PER_DAY = 12.0
_MAX_TIME_PAIRS_FOR_SUM = 4


def _is_plausible_daily_hours(hours: float) -> bool:
    return 0 <= hours <= MAX_HOURS_PER_DAY


def _segment_for_day(block: str, date_end: int) -> str:
    """Contexte texte d'un jour, sans déborder sur le total hebdo ni le jour suivant."""
    next_date = _DATE_RE.search(block, date_end + 1)
    segment_end = next_date.start() if next_date else min(len(block), date_end + 220)
    ctx = block[date_end:segment_end]
    total_idx = re.search(r"Total\s+pour\s+la\s+semaine", ctx, re.IGNORECASE)
    if total_idx:
        ctx = ctx[: total_idx.start()]
    return ctx


def _sum_time_pairs(segment: str) -> Optional[float]:
    """Repli : somme des plages horaires consécutives (8:00 12:00 13:00 17:30)."""
    pairs = _TIME_PAIR_RE.findall(segment)
    if len(pairs) < 2 or len(pairs) > _MAX_TIME_PAIRS_FOR_SUM:
        return None
    total_minutes = 0
    for i in range(0, len(pairs) - 1, 2):
        if i + 1 >= len(pairs):
            break
        h1, m1 = int(pairs[i][0]), int(pairs[i][1])
        h2, m2 = int(pairs[i + 1][0]), int(pairs[i + 1][1])
        if h1 >= 13 or h2 >= 13:
            continue
        start = h1 * 60 + m1
        end = h2 * 60 + m2
        if end > start:
            total_minutes += end - start
    if total_minutes <= 0:
        return None
    hours = round(total_minutes / 60.0, 2)
    return hours if _is_plausible_daily_hours(hours) else None


def _extract_day_hours(block: str, date_end: int) -> Optional[float]:
    """Total journalier : # H:MM, repli paires horaires, ou dernière H:MM plausible."""
    ctx = _segment_for_day(block, date_end)

    match = _DAY_MARKER_RE.search(ctx)
    if match:
        hours = _hhmm_to_hours(match.group(1), match.group(2))
        if _is_plausible_daily_hours(hours):
            return hours

    pair_sum = _sum_time_pairs(ctx)
    if pair_sum is not None:
        return pair_sum

    for h, m in reversed(_TIME_PAIR_RE.findall(ctx)):
        if int(h) >= 13:
            continue
        hours = _hhmm_to_hours(h, m)
        if _is_plausible_daily_hours(hours):
            return hours
    return None


def _expected_workdays_in_period(
    period_start: date | None, period_end: date | None
) -> int:
    if not period_start or not period_end:
        return 5
    count = 0
    current = period_start
    while current <= period_end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return max(count, 1)


def is_cegid_weekly_format(text: str) -> bool:
    if not text or len(text) < 200:
        return False
    if not _FORMAT_SIGNATURE.search(text):
        return False
    if not _PERIOD_HEADER.search(text):
        return False
    if not _WEEK_TOTAL_RE.search(text):
        return False
    return True


def _split_blocks(text: str) -> List[str]:
    indices = [m.start() for m in _BLOCK_HEADER_RE.finditer(text)]
    if not indices:
        return []
    blocks: List[str] = []
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(text)
        chunk = text[start:end]
        blocks.append(chunk)
    return blocks


def _parse_block(
    block: str,
    target_year: int,
    target_month: int,
    period_start: date | None,
    period_end: date | None,
) -> Optional[CegidEmployeeBlock]:
    header = _BLOCK_HEADER_RE.search(block)
    if not header:
        return None
    matricule = header.group(1).strip()
    raw_name = " ".join(header.group(2).split())

    if is_junk_employee_name(raw_name):
        return None

    total_match = _WEEK_TOTAL_RE.search(block)
    weekly_total: Optional[float] = None
    weekly_label: Optional[str] = None
    if total_match:
        weekly_label = f"{total_match.group(3)}:{total_match.group(4)}"
        weekly_total = _hhmm_to_hours(total_match.group(3), total_match.group(4))

    week_days: List[CegidDayEntry] = []
    target_days: List[CegidDayEntry] = []
    seen: set[tuple[int, int, int]] = set()
    parsed_in_period = 0

    for date_match in _DATE_RE.finditer(block):
        ctx_before = block[max(0, date_match.start() - 40) : date_match.start()]
        if re.search(r"Total\s+pour\s+la\s+semaine", ctx_before, re.IGNORECASE):
            continue
        d, mo, y_raw = (
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
        )
        y = _normalize_year(y_raw)
        key = (y, mo, d)
        if key in seen:
            continue
        try:
            day_date = date(y, mo, d)
        except ValueError:
            continue
        if period_start and period_end:
            if day_date < period_start or day_date > period_end:
                continue
        hours = _extract_day_hours(block, date_match.end())
        if hours is None:
            continue
        seen.add(key)
        entry = CegidDayEntry(jour=d, month=mo, year=y, heures=hours)
        week_days.append(entry)
        if day_date.weekday() < 5:
            parsed_in_period += 1
        if y == target_year and mo == target_month:
            target_days.append(entry)

    week_days.sort(key=lambda x: (x.year, x.month, x.jour))
    target_days.sort(key=lambda x: x.jour)

    expected = _expected_workdays_in_period(period_start, period_end)
    empty_week = (
        weekly_total is not None
        and weekly_total <= 0.001
        and (not week_days or all(d.heures <= 0.001 for d in week_days))
    )
    parse_failed = (
        weekly_total is not None
        and weekly_total > 0.001
        and not week_days
    )
    if empty_week:
        target_days = []
        week_days = []

    warnings: List[str] = []
    if parse_failed:
        warnings.append("Jours illisibles malgré un total PDF > 0 — vérifiez le scan.")
    elif weekly_total and weekly_total > 0.001 and parsed_in_period < expected * 0.6:
        warnings.append(
            f"Extraction partielle ({parsed_in_period}/{expected} jours ouvrés lus)."
        )

    return CegidEmployeeBlock(
        matricule=matricule,
        raw_name=raw_name,
        days=target_days if not empty_week else [],
        week_days=week_days,
        weekly_total_hours=weekly_total,
        weekly_total_label=weekly_label,
        empty_week=empty_week or parse_failed,
        parse_warnings=warnings,
        days_expected_count=expected,
        days_parsed_count=parsed_in_period,
    )


def try_parse_cegid_weekly(
    text: str,
    *,
    target_year: int,
    target_month: int,
) -> CegidParseResult:
    """Tente un parse Cegid hebdo. Retourne confidence 0 si format non reconnu."""
    result = CegidParseResult(format_detected=False, confidence=0.0)
    if not is_cegid_weekly_format(text):
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

    week_match = _WEEK_TOTAL_RE.search(text)
    if week_match and week_match.group(1) and week_match.group(2):
        result.week_number = int(week_match.group(1))
        result.week_year = int(week_match.group(2))

    blocks = _split_blocks(text)
    expected_blocks = len(_WEEK_TOTAL_RE.findall(text))
    parsed_blocks: List[CegidEmployeeBlock] = []

    for block in blocks:
        emp = _parse_block(
            block, target_year, target_month, period_start, period_end
        )
        if emp is not None:
            parsed_blocks.append(emp)

    result.employees = parsed_blocks

    if expected_blocks > 0:
        parse_ratio = len(parsed_blocks) / expected_blocks
    elif parsed_blocks:
        parse_ratio = 0.7
    else:
        parse_ratio = 0.0

    if parse_ratio >= 1.0:
        result.confidence = 0.95
    elif parse_ratio >= 0.85 and len(parsed_blocks) >= 1:
        result.confidence = 0.95
    elif parse_ratio >= 0.5 and len(parsed_blocks) >= 1:
        result.confidence = 0.75
    elif len(parsed_blocks) >= 1:
        result.confidence = 0.5
    else:
        result.confidence = 0.2
        result.parse_warnings.append(
            "Format Cegid détecté mais peu de blocs salariés exploitables."
        )

    if expected_blocks and len(parsed_blocks) < expected_blocks * 0.5:
        result.parse_warnings.append(
            f"{len(parsed_blocks)}/{expected_blocks} blocs salariés parsés — "
            "vérifiez la qualité OCR."
        )

    return result


def focus_week_index_for_period(
    year: int, month: int, period_start: date | None
) -> int | None:
    """Index 0-based de la semaine du mois contenant period_start (aligné planning UI)."""
    if period_start is None:
        return None
    if period_start.year != year or period_start.month != month:
        return None
    days_in_month = cal_mod.monthrange(year, month)[1]
    first_dow = date(year, month, 1).weekday()
    weeks: List[List[int]] = []
    current: List[int] = [0] * first_dow
    for d in range(1, days_in_month + 1):
        current.append(d)
        if len(current) == 7:
            weeks.append(current)
            current = []
    if current:
        while len(current) < 7:
            current.append(0)
        weeks.append(current)

    for idx, week in enumerate(weeks):
        if period_start.day in week:
            return idx
    return None


__all__ = [
    "CegidDayEntry",
    "CegidEmployeeBlock",
    "CegidParseResult",
    "focus_week_index_for_period",
    "is_cegid_weekly_format",
    "try_parse_cegid_weekly",
]
