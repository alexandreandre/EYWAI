"""
Détection déterministe de la période couverte par un relevé de pointeuse (OCR).

Analyse le texte extrait avant l'appel LLM pour estimer si le document est
hebdomadaire ou mensuel, en extraire les dates explicites et produire des
alertes si la période ne correspond pas au mois cible de l'UI.
"""

from __future__ import annotations

import calendar as cal_mod
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Literal, Optional, Tuple

TimesheetScope = Literal["weekly", "monthly", "unknown"]
TimesheetConfidence = Literal["high", "medium", "low"]

_WEEK_RANGE_RE = re.compile(
    r"semaine\s+du\s+"
    r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?"
    r"\s+au\s+"
    r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?",
    re.IGNORECASE,
)
_DU_AU_RANGE_RE = re.compile(
    r"\bdu\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?"
    r"\s+au\s+"
    r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?",
    re.IGNORECASE,
)
_WEEK_NUM_RE = re.compile(
    r"\b(?:semaine|week)\s*(?:n[°o.]?\s*)?(\d{1,2})\b",
    re.IGNORECASE,
)
_ISO_WEEK_RE = re.compile(r"\bS(\d{1,2})\b")
_DATE_DMY_RE = re.compile(
    r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b"
)
_WEEKDAY_WITH_DATE_RE = re.compile(
    r"\b(lun|mar|mer|jeu|ven|sam|dim|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)"
    r"\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?",
    re.IGNORECASE,
)

_MONTHS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}
_DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS_FR.keys()) + r")(?:\s+(\d{4}))?",
    re.IGNORECASE,
)


@dataclass
class TimesheetPeriodDetection:
    scope: TimesheetScope = "unknown"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    confidence: TimesheetConfidence = "low"
    warnings: List[str] = field(default_factory=list)
    detected_dates: List[date] = field(default_factory=list)


def _normalize_year(year_raw: Optional[str], default_year: int) -> int:
    if not year_raw:
        return default_year
    y = int(year_raw)
    if y < 100:
        y += 2000
    return y


def _parse_dmy(
    day: str, month: str, year_raw: Optional[str], default_year: int
) -> Optional[date]:
    try:
        d, m = int(day), int(month)
        y = _normalize_year(year_raw, default_year)
        return date(y, m, d)
    except ValueError:
        return None


def _extract_dates_from_text(text: str, default_year: int) -> List[date]:
    found: List[date] = []
    seen: set[date] = set()

    for match in _DATE_DMY_RE.finditer(text):
        parsed = _parse_dmy(match.group(1), match.group(2), match.group(3), default_year)
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append(parsed)

    for match in _WEEKDAY_WITH_DATE_RE.finditer(text):
        parsed = _parse_dmy(match.group(2), match.group(3), match.group(4), default_year)
        if parsed and parsed not in seen:
            seen.add(parsed)
            found.append(parsed)

    for match in _DATE_TEXT_RE.finditer(text):
        day = int(match.group(1))
        month_name = match.group(2).lower()
        month = _MONTHS_FR.get(month_name.replace("é", "e").replace("û", "u"))
        if not month:
            month = _MONTHS_FR.get(match.group(2).lower())
        if not month:
            continue
        y = _normalize_year(match.group(3), default_year)
        try:
            parsed = date(y, month, day)
            if parsed not in seen:
                seen.add(parsed)
                found.append(parsed)
        except ValueError:
            continue

    found.sort()
    return found


def _range_from_match(
    match: re.Match[str], default_year: int
) -> Optional[Tuple[date, date]]:
    start = _parse_dmy(match.group(1), match.group(2), match.group(3), default_year)
    end = _parse_dmy(match.group(4), match.group(5), match.group(6), default_year)
    if start and end:
        if end < start:
            start, end = end, start
        return start, end
    return None


_MAX_PLAUSIBLE_HEADER_SPAN = 45
_NEAR_TARGET_MARGIN_MONTHS = 2


def _months_apart(d: date, target_year: int, target_month: int) -> int:
    return abs((d.year - target_year) * 12 + (d.month - target_month))


def _filter_dates_near_target(
    dates: List[date], target_year: int, target_month: int
) -> List[date]:
    """Écarte le bruit OCR (dates hors du contexte du mois affiché)."""
    near = [
        d
        for d in dates
        if _months_apart(d, target_year, target_month) <= _NEAR_TARGET_MARGIN_MONTHS
    ]
    return near if near else dates


def _plausible_explicit_range(
    explicit_range: Tuple[date, date],
    target_year: int,
    target_month: int,
) -> bool:
    start, end = explicit_range
    span = (end - start).days + 1
    if span > _MAX_PLAUSIBLE_HEADER_SPAN:
        return False
    target_start = date(target_year, target_month, 1)
    target_end = date(
        target_year, target_month, cal_mod.monthrange(target_year, target_month)[1]
    )
    if end < target_start - timedelta(days=62) or start > target_end + timedelta(days=62):
        return False
    return True


def _refine_detection_bounds(
    result: TimesheetPeriodDetection,
    target_year: int,
    target_month: int,
) -> None:
    """Affine start/end à partir des dates crédibles proches du mois cible."""
    if result.detected_dates:
        result.detected_dates = _filter_dates_near_target(
            result.detected_dates, target_year, target_month
        )
    if result.start_date and result.end_date:
        span = (result.end_date - result.start_date).days + 1
        if span > _MAX_PLAUSIBLE_HEADER_SPAN:
            if result.detected_dates:
                result.start_date = result.detected_dates[0]
                result.end_date = result.detected_dates[-1]
            else:
                result.start_date = None
                result.end_date = None
                return
        elif _months_apart(result.start_date, target_year, target_month) > _NEAR_TARGET_MARGIN_MONTHS:
            if result.detected_dates:
                result.start_date = result.detected_dates[0]
                result.end_date = result.detected_dates[-1]
    elif result.detected_dates:
        result.start_date = result.detected_dates[0]
        result.end_date = result.detected_dates[-1]


def detect_timesheet_period(
    text: str,
    *,
    target_year: int,
    target_month: int,
    document_scope: str = "auto",
) -> TimesheetPeriodDetection:
    """Estime la période couverte par le relevé OCR."""
    result = TimesheetPeriodDetection()
    if not (text or "").strip():
        result.warnings.append("Texte du relevé vide ou illisible.")
        return result

    explicit_range: Optional[Tuple[date, date]] = None
    week_range = _WEEK_RANGE_RE.search(text)
    if week_range:
        explicit_range = _range_from_match(week_range, target_year)
    if explicit_range is None:
        du_au = _DU_AU_RANGE_RE.search(text)
        if du_au:
            explicit_range = _range_from_match(du_au, target_year)

    dates = _extract_dates_from_text(text, target_year)
    if explicit_range and _plausible_explicit_range(
        explicit_range, target_year, target_month
    ):
        start, end = explicit_range
        result.start_date = start
        result.end_date = end
        result.scope = "weekly"
        result.confidence = "high"
        span = (end - start).days + 1
        if span > 10:
            result.scope = "monthly" if span > 20 else "weekly"
    elif dates:
        result.detected_dates = dates
        result.start_date = dates[0]
        result.end_date = dates[-1]
        span = (dates[-1] - dates[0]).days + 1
        unique_days = len({d.isoformat() for d in dates})
        if span <= 8 and unique_days <= 7:
            result.scope = "weekly"
            result.confidence = "high" if unique_days >= 3 else "medium"
        elif span > 20 or unique_days > 15:
            result.scope = "monthly"
            result.confidence = "medium" if unique_days >= 10 else "low"
        else:
            result.scope = "unknown"
            result.confidence = "medium"
    elif _WEEK_NUM_RE.search(text) or _ISO_WEEK_RE.search(text):
        result.scope = "weekly"
        result.confidence = "low"
        result.warnings.append(
            "Numéro de semaine détecté sans dates explicites — précisez "
            "« Semaine commençant le » si les jours semblent incorrects."
        )
    else:
        result.scope = "unknown"
        result.confidence = "low"
        result.warnings.append(
            "Aucune date explicite détectée dans le relevé. "
            "Indiquez le type « Hebdomadaire » et la date de début de semaine."
        )

    if document_scope == "weekly":
        result.scope = "weekly"
        if result.confidence == "low":
            result.confidence = "medium"
    elif document_scope == "monthly":
        result.scope = "monthly"

    result.detected_dates = dates or (
        _dates_in_range(result.start_date, result.end_date)
        if result.start_date and result.end_date
        else []
    )

    _refine_detection_bounds(result, target_year, target_month)

    result.warnings.extend(
        _compare_with_target_month(result, target_year, target_month)
    )
    return result


def _dates_in_range(start: date, end: date) -> List[date]:
    days: List[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _compare_with_target_month(
    detection: TimesheetPeriodDetection, target_year: int, target_month: int
) -> List[str]:
    warnings: List[str] = []
    if not detection.start_date or not detection.end_date:
        return warnings

    target_start = date(target_year, target_month, 1)
    target_end = date(
        target_year, target_month, cal_mod.monthrange(target_year, target_month)[1]
    )

    if detection.end_date < target_start or detection.start_date > target_end:
        warnings.append(
            f"Le relevé semble couvrir le {_fmt_fr(detection.start_date)} au "
            f"{_fmt_fr(detection.end_date)}, hors du mois affiché "
            f"({_month_name(target_month)} {target_year}). "
            "Changez de mois avant d'enregistrer."
        )
        return warnings

    if detection.scope == "weekly" and detection.confidence in ("high", "medium"):
        in_target = [
            d
            for d in detection.detected_dates
            if d.year == target_year and d.month == target_month
        ]
        if in_target and len(in_target) <= 7:
            pass  # OK, relevé hebdo partiel attendu
    return warnings


def align_period_warnings(
    detection: TimesheetPeriodDetection, target_year: int, target_month: int
) -> TimesheetPeriodDetection:
    """Recalcule les alertes période pour un mois cible (après auto-correction)."""
    detection.warnings = _compare_with_target_month(
        detection, target_year, target_month
    )
    return detection


def _fmt_fr(d: date) -> str:
    return f"{d.day} {_month_name(d.month)} {d.year}"


def _month_name(month: int) -> str:
    names = [
        "",
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ]
    return names[month] if 1 <= month <= 12 else str(month)


def format_period_context(
    detection: TimesheetPeriodDetection, target_year: int, target_month: int
) -> str:
    """Bloc texte injecté dans le prompt LLM."""
    lines = [
        "Contexte période du relevé :",
        f"- Portée estimée : {detection.scope} (confiance {detection.confidence}).",
    ]
    if detection.start_date and detection.end_date:
        lines.append(
            f"- Période détectée : du {_fmt_fr(detection.start_date)} "
            f"au {_fmt_fr(detection.end_date)}."
        )
    if detection.detected_dates:
        in_month = [
            d.day
            for d in detection.detected_dates
            if d.year == target_year and d.month == target_month
        ]
        if in_month:
            lines.append(
                f"- Dates explicites dans le mois cible ({target_month}/{target_year}) : "
                f"jours {', '.join(str(j) for j in sorted(set(in_month)))}."
            )
    lines.extend(
        [
            "- Si le relevé ne couvre qu'une semaine ou une partie du mois, "
            "n'extraire QUE les jours mentionnés.",
            "- Utiliser les dates EXPLICITES du document pour le champ `jour`, "
            "pas la position des colonnes Lun–Ven dans le tableau.",
            "- Ne pas inventer de jours absents du relevé.",
        ]
    )
    return "\n".join(lines)


def format_week_anchor_context(anchor: date, target_year: int, target_month: int) -> str:
    """Ancrage manuel : mappe Lun→Dim à partir d'une date de début."""
    weekday_labels = [
        "lundi",
        "mardi",
        "mercredi",
        "jeudi",
        "vendredi",
        "samedi",
        "dimanche",
    ]
    lines = [
        f"Ancrage hebdomadaire : la semaine commence le {_fmt_fr(anchor)}.",
        "Correspondance colonnes → numéro de jour du mois cible :",
    ]
    for offset in range(7):
        d = anchor + timedelta(days=offset)
        wd = weekday_labels[d.weekday()]
        if d.year == target_year and d.month == target_month:
            lines.append(f"  - {wd} → jour {d.day}")
        else:
            lines.append(
                f"  - {wd} ({d.day}/{d.month}) → hors mois cible, ignorer"
            )
    lines.append(
        "Si le relevé n'affiche que Lun/Mar/Mer… sans dates, utiliser cette "
        "correspondance pour déterminer `jour`."
    )
    return "\n".join(lines)


def suggested_target_month(
    detection: TimesheetPeriodDetection,
) -> Optional[Tuple[int, int]]:
    """Mois/année suggérés si le relevé est hors du mois affiché."""
    if not detection.start_date:
        return None
    return detection.start_date.year, detection.start_date.month


def resolve_effective_target_month(
    detection: TimesheetPeriodDetection,
    requested_year: int,
    requested_month: int,
) -> Tuple[int, int, bool, Optional[str]]:
    """Détermine le mois d'analyse effectif.

    Bascule automatiquement lorsque la période détectée est entièrement contenue
    dans un autre mois unique (confiance medium ou high).
    """
    if not detection.start_date or not detection.end_date:
        return requested_year, requested_month, False, None
    if detection.confidence == "low":
        return requested_year, requested_month, False, None

    target_start = date(requested_year, requested_month, 1)
    target_end = date(
        requested_year,
        requested_month,
        cal_mod.monthrange(requested_year, requested_month)[1],
    )

    if not (detection.end_date < target_start or detection.start_date > target_end):
        return requested_year, requested_month, False, None

    if (
        detection.start_date.year == detection.end_date.year
        and detection.start_date.month == detection.end_date.month
    ):
        eff_year = detection.start_date.year
        eff_month = detection.start_date.month
        msg = (
            f"Le relevé couvre {_month_name(eff_month)} {eff_year} "
            f"(du {_fmt_fr(detection.start_date)} au {_fmt_fr(detection.end_date)}). "
            f"Le calendrier a été basculé automatiquement depuis "
            f"{_month_name(requested_month)} {requested_year}."
        )
        return eff_year, eff_month, True, msg

    return requested_year, requested_month, False, None


__all__ = [
    "TimesheetPeriodDetection",
    "TimesheetScope",
    "TimesheetConfidence",
    "align_period_warnings",
    "detect_timesheet_period",
    "format_period_context",
    "format_week_anchor_context",
    "resolve_effective_target_month",
    "suggested_target_month",
]
