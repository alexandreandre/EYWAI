"""
Analyse déterministe rapide des instructions de calendrier (sans LLM).

Utilisée uniquement lorsque l'instruction est non ambiguë : un employé
identifié, des heures explicites et des jours clairement délimités.
Sinon, retourne None et le flux LLM prend le relais.
"""

from __future__ import annotations

import calendar as cal_mod
import re
from typing import List, Optional

from app.modules.schedules.application.ai_fill import (
    _VALID_NATURES,
    _WEEKDAYS_FR,
    _build_broadcast_proposal,
    _build_proposal,
    _normalize,
    _resolve_employee,
)
from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee

_HOUR_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*h(?:eures?)?", re.IGNORECASE)
_DAY_RANGE_NUM_RE = re.compile(
    r"du\s+(\d{1,2})(?:er)?\s+au\s+(\d{1,2})(?:er)?",
    re.IGNORECASE,
)
_SINGLE_DAY_RE = re.compile(r"\ble\s+(\d{1,2})(?:er)?\b", re.IGNORECASE)
_WEEKDAY_RANGE_RE = re.compile(
    r"du\s+(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)"
    r"\s+au\s+(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)",
    re.IGNORECASE,
)

_PREVU_HINTS = (
    "prevu",
    "prevue",
    "prevues",
    "planning",
    "planifie",
    "planifies",
    "theorique",
    "previsionnel",
)
_REEL_HINTS = (
    "fait",
    "faite",
    "faites",
    "realise",
    "realises",
    "effectue",
    "pointage",
    "travaille",
    "travaillees",
    "a travaille",
)

_BROADCAST_PHRASES = (
    "tout le monde",
    "tous les collaborateurs",
    "tous les salaries",
    "everyone",
)


def _detect_nature(instruction: str) -> str:
    norm = _normalize(instruction)
    has_prevu = any(h in norm for h in _PREVU_HINTS)
    has_reel = any(h in norm for h in _REEL_HINTS)
    if has_prevu and not has_reel:
        return "prevu"
    if has_reel and not has_prevu:
        return "reel"
    return "reel"


def _extract_hours(instruction: str) -> Optional[float]:
    matches = _HOUR_RE.findall(instruction)
    if not matches:
        return None
    values = {float(m.replace(",", ".")) for m in matches}
    if len(values) != 1:
        return None
    return values.pop()


def _employees_mentioned(instruction: str, roster: List[RosterEmployee]) -> List[RosterEmployee]:
    norm_inst = _normalize(instruction)
    found: List[RosterEmployee] = []
    seen: set[str] = set()

    for emp in roster:
        full_a = _normalize(f"{emp.first_name} {emp.last_name}")
        full_b = _normalize(f"{emp.last_name} {emp.first_name}")
        last = _normalize(emp.last_name)
        first = _normalize(emp.first_name)

        matched = False
        if full_a in norm_inst or full_b in norm_inst:
            matched = True
        elif len(last) >= 3 and re.search(rf"\b{re.escape(last)}\b", norm_inst):
            same_last = [
                e for e in roster if _normalize(e.last_name) == last
            ]
            if len(same_last) == 1:
                matched = True
        elif len(first) >= 3 and re.search(rf"\b{re.escape(first)}\b", norm_inst):
            same_first = [
                e for e in roster if _normalize(e.first_name) == first
            ]
            if len(same_first) == 1:
                matched = True

        if matched and emp.id not in seen:
            seen.add(emp.id)
            found.append(emp)

    return found


def _weekday_index(name: str) -> int:
    return _WEEKDAYS_FR.index(name.lower())


def _days_in_weekday_range(
    year: int, month: int, start_wd: int, end_wd: int
) -> List[int]:
    num_days = cal_mod.monthrange(year, month)[1]
    days: List[int] = []
    for day in range(1, num_days + 1):
        wd = cal_mod.weekday(year, month, day)
        if start_wd <= end_wd:
            if start_wd <= wd <= end_wd:
                days.append(day)
        elif wd >= start_wd or wd <= end_wd:
            days.append(day)
    return days


def _extract_days(instruction: str, year: int, month: int) -> Optional[List[int]]:
    num_days = cal_mod.monthrange(year, month)[1]
    norm = _normalize(instruction)

    if "tous les jours ouvres" in norm or "jours ouvres" in norm:
        return [
            d
            for d in range(1, num_days + 1)
            if cal_mod.weekday(year, month, d) < 5
        ]

    weekday_match = _WEEKDAY_RANGE_RE.search(instruction)
    if weekday_match:
        start_wd = _weekday_index(weekday_match.group(1))
        end_wd = _weekday_index(weekday_match.group(2))
        days = _days_in_weekday_range(year, month, start_wd, end_wd)
        return days or None

    num_range = _DAY_RANGE_NUM_RE.search(instruction)
    if num_range:
        start, end = int(num_range.group(1)), int(num_range.group(2))
        if 1 <= start <= end <= num_days:
            return list(range(start, end + 1))

    singles = [int(m.group(1)) for m in _SINGLE_DAY_RE.finditer(instruction)]
    if singles:
        valid = sorted({d for d in singles if 1 <= d <= num_days})
        return valid or None

    return None


def is_broadcast_instruction(instruction: str) -> bool:
    """Détecte une consigne collective (« tout le monde », « à tous », etc.)."""
    norm = _normalize(instruction)
    if any(phrase in norm for phrase in _BROADCAST_PHRASES):
        return True
    if "tous les jours" in norm:
        return False
    return bool(re.search(r"\b(?:a|pour)\s+tous\b", norm))


def excluded_employees_from_instruction(
    instruction: str, roster: List[RosterEmployee]
) -> List[RosterEmployee]:
    """Employés cités après « sauf » / « except » dans la consigne."""
    match = re.search(r"\b(?:sauf|except)\b(.+)", instruction, re.IGNORECASE)
    if not match:
        return []
    return _employees_mentioned(match.group(1), roster)


def _all_month_days(year: int, month: int) -> List[int]:
    num_days = cal_mod.monthrange(year, month)[1]
    return list(range(1, num_days + 1))


def _try_fast_parse_broadcast(
    *,
    year: int,
    month: int,
    instruction: str,
    roster: List[RosterEmployee],
    force: bool = False,
) -> Optional[AiCalendarProposalResponse]:
    # `force` : mode collectif explicite (bouton « À saisir »), on diffuse même
    # sans formule « tout le monde » dans la consigne.
    if not force and not is_broadcast_instruction(instruction):
        return None

    hours = _extract_hours(instruction)
    if hours is None:
        return None

    days = _extract_days(instruction, year, month) or _all_month_days(year, month)
    excluded_ids = {e.id for e in excluded_employees_from_instruction(instruction, roster)}
    targets = [e for e in roster if e.id not in excluded_ids]
    if not targets:
        return None

    nature = _detect_nature(instruction)
    if nature not in _VALID_NATURES:
        nature = "reel"

    extracted = {
        "employees": [
            {
                "name": "(tous)",
                "days": [
                    {
                        "jour": day,
                        "heures": hours,
                        "type": "travail",
                        "nature": nature,
                    }
                    for day in days
                ],
            }
        ],
        "warnings": [],
    }
    return _build_broadcast_proposal(
        year=year,
        month=month,
        source="texte (analyse rapide)",
        extracted=extracted,
        roster=targets,
        default_nature=nature,
    )


def try_fast_parse_instruction(
    *,
    year: int,
    month: int,
    instruction: str,
    roster: List[RosterEmployee],
    force_broadcast: bool = False,
) -> Optional[AiCalendarProposalResponse]:
    """
    Tente une analyse locale sans LLM. Retourne None si l'instruction est
    trop ambiguë pour une interprétation fiable.

    Si `force_broadcast` est vrai (mode « À saisir » collectif), on ne tente
    QUE la diffusion à tout le roster : jamais de résolution sur un seul nom.
    """
    text = (instruction or "").strip()
    if not text or not roster:
        return None

    broadcast = _try_fast_parse_broadcast(
        year=year,
        month=month,
        instruction=text,
        roster=roster,
        force=force_broadcast,
    )
    if broadcast is not None:
        return broadcast

    # En mode collectif forcé, on ne retombe pas sur la résolution mono-nom :
    # si l'analyse rapide n'a pas suffi, on laisse le LLM diffuser à tous.
    if force_broadcast:
        return None

    hours = _extract_hours(text)
    if hours is None:
        return None

    mentioned = _employees_mentioned(text, roster)
    if len(mentioned) != 1:
        return None

    days = _extract_days(text, year, month)
    if not days:
        return None

    nature = _detect_nature(text)
    if nature not in _VALID_NATURES:
        nature = "reel"

    emp = mentioned[0]
    display_name = f"{emp.first_name} {emp.last_name}"
    proposal = _resolve_employee(display_name, roster)
    if proposal.employee_id is None:
        return None

    extracted = {
        "employees": [
            {
                "name": display_name,
                "days": [
                    {
                        "jour": day,
                        "heures": hours,
                        "type": "travail",
                        "nature": nature,
                    }
                    for day in days
                ],
            }
        ],
        "warnings": [],
    }

    result = _build_proposal(
        year=year,
        month=month,
        source="texte (analyse rapide)",
        extracted=extracted,
        roster=roster,
        default_nature=nature,
    )
    if not result.employees:
        return None
    return result


__all__ = [
    "excluded_employees_from_instruction",
    "is_broadcast_instruction",
    "try_fast_parse_instruction",
]
