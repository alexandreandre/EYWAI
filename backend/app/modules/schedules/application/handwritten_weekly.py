"""Post-traitement des feuilles hebdomadaires manuscrites DEBUT/FIN."""

from __future__ import annotations

import copy
import re
import unicodedata
from datetime import date
from datetime import timedelta
from typing import Any

from app.modules.schedules.domain.punch_accounting_entities import (
    PunchAccountingSettings,
)
from app.modules.schedules.domain.punch_accounting_rules import apply_break_threshold

FORMAT_HINT = "handwritten_weekly"

_WEEK_RE = re.compile(r"\bS\s*(\d{1,2})\b", re.IGNORECASE)
_CEGID_SIGNATURE_RE = re.compile(
    r"pointages?\s+[\"']?retenu|semaine\s+[àa]\s+semaine|\bmatricule\b",
    re.IGNORECASE,
)
_WEEKDAY_INDEX = {
    "lundi": 1,
    "mardi": 2,
    "mercredi": 3,
    "jeudi": 4,
    "vendredi": 5,
    "samedi": 6,
    "dimanche": 7,
}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def detect_handwritten_weekly_text(text: str) -> bool:
    """Détecte une feuille hebdo générique, sans dépendre d'un client."""
    if not text:
        return False
    upper = text.upper()
    weekdays = sum(
        1 for d in ("LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI") if d in upper
    )
    return (
        "DEBUT" in upper
        and "FIN" in upper
        and weekdays >= 3
        and _WEEK_RE.search(upper) is not None
        and _CEGID_SIGNATURE_RE.search(text) is None
    )


def detect_handwritten_weekly_payload(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    hint = str(data.get("page_period_hint") or "")
    has_week = _WEEK_RE.search(hint) is not None
    handwritten_days = 0
    employees = data.get("employees") or []
    for emp in employees:
        if emp.get("week_number"):
            has_week = True
        for day in emp.get("days") or []:
            if day.get("weekday") is not None or day.get("debut") or day.get("fin"):
                handwritten_days += 1
    return has_week and handwritten_days > 0


def is_handwritten_weekly_format(format_hint: str | None) -> bool:
    return (format_hint or "").lower() == FORMAT_HINT


def week_number_from_hint(value: str | None) -> int | None:
    if not value:
        return None
    match = _WEEK_RE.search(value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def weekday_to_month_day(
    *,
    year: int,
    month: int,
    week_number: int,
    weekday: str | int | None,
) -> int | None:
    if weekday is None:
        return None
    if isinstance(weekday, int):
        iso_weekday = weekday + 1 if 0 <= weekday <= 6 else weekday
    else:
        iso_weekday = _WEEKDAY_INDEX.get(_normalize(str(weekday)))
    if not iso_weekday:
        return None
    try:
        day = date.fromisocalendar(year, week_number, iso_weekday)
    except ValueError:
        return None
    iso_monday = date.fromisocalendar(year, week_number, 1)
    first_of_month = date(year, month, 1)
    if (
        iso_monday < first_of_month
        and iso_monday.month != month
        and (iso_monday + timedelta(days=4)).month == month
    ):
        # Feuilles Sxx sans dates : éviter une semaine presque vide dans l'UI
        # lorsque l'en-tête désigne la semaine qui bascule en début de mois.
        day += timedelta(days=7)
    if day.month != month:
        return None
    return day.day


def _parse_time(value: Any) -> int | None:
    if value is None:
        return None
    text = _normalize(str(value)).replace("h", ":").replace(",", ":").replace(".", ":")
    match = re.search(r"\b(\d{1,2})(?::(\d{1,2}))?\b", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def calculate_hours_from_range(
    debut: Any,
    fin: Any,
    *,
    settings: PunchAccountingSettings | None = None,
) -> float | None:
    """Calcule FIN-DEBUT, pause déduite selon le paramétrage de la société.

    Quand la comptabilisation des pointages est activée, la pause vient des
    réglages société (pause par défaut et seuil de présence), comme sur les
    journées badgées : une feuille papier et un badgeage donnent alors le même
    résultat pour la même journée.

    Sans paramétrage, on retombe sur l'heure forfaitaire des feuilles
    manuscrites, où un créneau unique matin+après-midi inclut souvent la pause.
    """
    start = _parse_time(debut)
    end = _parse_time(fin)
    if start is None or end is None or end <= start:
        return None
    duration = end - start
    if settings is not None and settings.enabled:
        duration -= apply_break_threshold(
            settings.default_break_deduct_minutes, start, end, settings
        )
    elif start < 12 * 60 and end >= 15 * 60 and duration >= 8 * 60 + 30:
        duration -= 60
    return round(max(0, duration) / 60.0, 2)


def normalize_handwritten_weekly_payload(
    data: dict[str, Any] | None,
    *,
    year: int,
    month: int,
    settings: PunchAccountingSettings | None = None,
) -> dict[str, Any] | None:
    if not data:
        return data
    normalized = copy.deepcopy(data)
    fallback_week = week_number_from_hint(str(normalized.get("page_period_hint") or ""))
    for emp in normalized.get("employees") or []:
        week_number = emp.get("week_number") or fallback_week
        try:
            week_number = int(week_number) if week_number is not None else None
        except (TypeError, ValueError):
            week_number = None
        kept_days: list[dict[str, Any]] = []
        for day in emp.get("days") or []:
            item = dict(day)
            if item.get("jour") is None and week_number is not None:
                item["jour"] = weekday_to_month_day(
                    year=year,
                    month=month,
                    week_number=week_number,
                    weekday=item.get("weekday"),
                )
            # Avec un paramétrage société, le calcul serveur prime sur les heures
            # rendues par l'IA : elle applique sa propre pause forfaitaire.
            recompute = item.get("heures") is None or (
                settings is not None and settings.enabled
            )
            if recompute:
                heures = calculate_hours_from_range(
                    item.get("debut"),
                    item.get("fin"),
                    settings=settings,
                )
                if heures is not None or item.get("heures") is None:
                    item["heures"] = heures
            item["type"] = item.get("type") or "travail"
            if item.get("jour") is not None:
                kept_days.append(item)
        emp["days"] = kept_days
        if emp.get("matricule") in ("", "null"):
            emp["matricule"] = None
    return normalized


__all__ = [
    "FORMAT_HINT",
    "calculate_hours_from_range",
    "detect_handwritten_weekly_payload",
    "detect_handwritten_weekly_text",
    "is_handwritten_weekly_format",
    "normalize_handwritten_weekly_payload",
    "weekday_to_month_day",
    "week_number_from_hint",
]
