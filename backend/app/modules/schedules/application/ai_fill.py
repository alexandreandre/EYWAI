"""
Saisie assistée du calendrier (page Calendriers RH) — couche application.

Produit une proposition d'heures par employé et par jour, à partir :
- d'une instruction en langage naturel (texte ou dictée transcrite côté client) ;
- d'un relevé de pointeuse (PDF / image) lu par OCR.

Chaque jour est qualifié par sa `nature` : heures « prevu » (prévues, planning)
ou « reel » (faites, réalisées). L'IA déduit cette nature du libellé/du document.

Aucune écriture en base ici : la proposition est revue par le RH dans le front,
qui persiste vers le calendrier prévu et/ou les heures réelles selon la nature.
"""

from __future__ import annotations

import calendar as cal_mod
import logging
import unicodedata
from typing import Any, Dict, List

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
    RosterEmployee,
)
from app.shared.infrastructure.ai import (
    MODEL_SCHEDULE_NL_FILL,
    MODEL_TIMESHEET_EXTRACTION,
    is_llm_configured,
)
from app.shared.infrastructure.ai.structured_extractor import extract_structured_json
from app.shared.infrastructure.documents import (
    DocumentExtractionError,
    extract_document_text,
)

logger = logging.getLogger(__name__)

_WEEKDAYS_FR = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]

_VALID_TYPES = {
    "travail",
    "weekend",
    "conge",
    "ferie",
    "arret_maladie",
    "absence",
}

_VALID_NATURES = {"prevu", "reel"}

# Schéma JSON strict (OpenRouter exige additionalProperties=false et required complet)
_PROPOSAL_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "employees": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "jour": {"type": "integer"},
                                "heures": {"type": ["number", "null"]},
                                "type": {"type": "string"},
                                "nature": {
                                    "type": "string",
                                    "enum": ["prevu", "reel"],
                                },
                            },
                            "required": ["jour", "heures", "type", "nature"],
                        },
                    },
                },
                "required": ["name", "days"],
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["employees", "warnings"],
}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


def _month_calendar_anchor(year: int, month: int) -> str:
    """Ancre calendaire compacte (évite d'énumérer chaque jour du mois)."""
    num_days = cal_mod.monthrange(year, month)[1]
    first_weekday = _WEEKDAYS_FR[cal_mod.weekday(year, month, 1)]
    return (
        f"Le 1er est un {first_weekday}. Le mois compte {num_days} jours "
        f"(jour 1 à {num_days})."
    )


def _build_system_prompt(year: int, month: int, default_nature: str) -> str:
    num_days = cal_mod.monthrange(year, month)[1]
    return (
        "Assistant RH : convertis une consigne d'heures en JSON pour un calendrier "
        "de paie mensuel français.\n"
        f"Période : {month}/{year}. {_month_calendar_anchor(year, month)}\n\n"
        "Champs par jour : jour (1-" + str(num_days) + "), heures (nombre ou null), "
        "type (travail|conge|ferie|arret_maladie|absence|weekend), "
        "nature (prevu|reel).\n"
        "- prevu = heures planifiées ; reel = heures faites / pointage.\n"
        f"- Par défaut nature='{default_nature}' si non précisé.\n"
        "- Même date peut avoir prevu et reel si la consigne le distingue.\n"
        "- Ne crée aucun employé ni jour non mentionné.\n"
        "- Recopie name tel qu'écrit dans la consigne.\n"
        "- warnings : ambiguïtés (nom, heures, nature)."
    )


def _roster_hint_for_text(roster: List[RosterEmployee], limit: int = 30) -> str:
    """Liste compacte d'employés pour le LLM (résolution finale côté serveur)."""
    return "; ".join(f"{e.first_name} {e.last_name}" for e in roster[:limit])


def _roster_matching_document(
    text: str, roster: List[RosterEmployee], *, limit: int = 40
) -> List[RosterEmployee]:
    """Ne garde que les employés dont le nom apparaît dans le document OCR."""
    norm_text = _normalize(text)
    if not norm_text:
        return roster[:limit]
    matched: List[RosterEmployee] = []
    for emp in roster:
        full = _normalize(f"{emp.first_name} {emp.last_name}")
        last = _normalize(emp.last_name)
        first = _normalize(emp.first_name)
        if full in norm_text:
            matched.append(emp)
        elif len(last) >= 3 and last in norm_text:
            matched.append(emp)
        elif len(first) >= 3 and first in norm_text:
            matched.append(emp)
    return matched if matched else roster[:limit]


_MAX_TIMESHEET_TEXT_CHARS = 14_000


def _resolve_employee(raw_name: str, roster: List[RosterEmployee]) -> AiEmployeeProposal:
    """Associe un nom brut à un employé du roster (matching déterministe)."""
    proposal = AiEmployeeProposal(raw_name=raw_name)
    norm_raw = _normalize(raw_name)
    if not norm_raw or not roster:
        return proposal

    raw_tokens = set(norm_raw.split())

    exact_matches = []
    partial_matches = []
    for emp in roster:
        full_a = _normalize(f"{emp.first_name} {emp.last_name}")
        full_b = _normalize(f"{emp.last_name} {emp.first_name}")
        if norm_raw in (full_a, full_b):
            exact_matches.append(emp)
            continue
        emp_tokens = set(full_a.split())
        if raw_tokens and raw_tokens.issubset(emp_tokens):
            partial_matches.append(emp)
        elif emp_tokens & raw_tokens:
            # au moins un token (nom ou prénom) en commun
            partial_matches.append(emp)

    if len(exact_matches) == 1:
        emp = exact_matches[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "high"
    elif len(partial_matches) == 1:
        emp = partial_matches[0]
        proposal.employee_id = emp.id
        proposal.matched_name = f"{emp.first_name} {emp.last_name}"
        proposal.match_confidence = "medium"
    else:
        if len(exact_matches) > 1 or len(partial_matches) > 1:
            proposal.warnings.append(
                f"Plusieurs employés correspondent à « {raw_name} », à confirmer."
            )
        else:
            proposal.warnings.append(
                f"Aucun employé reconnu pour « {raw_name} »."
            )
    return proposal


def _coerce_days(
    raw_days: List[Dict[str, Any]], num_days: int, default_nature: str
) -> List[AiDayEntry]:
    days: List[AiDayEntry] = []
    seen: set[tuple[int, str]] = set()
    for raw in raw_days or []:
        try:
            jour = int(raw.get("jour"))
        except (TypeError, ValueError):
            continue
        if jour < 1 or jour > num_days:
            continue
        nature = str(raw.get("nature") or default_nature).strip().lower()
        if nature not in _VALID_NATURES:
            nature = default_nature
        if (jour, nature) in seen:
            continue
        seen.add((jour, nature))
        day_type = str(raw.get("type") or "travail").strip().lower()
        if day_type not in _VALID_TYPES:
            day_type = "travail"
        heures = raw.get("heures")
        try:
            heures_val = None if heures is None else float(heures)
        except (TypeError, ValueError):
            heures_val = None
        if heures_val is not None and heures_val < 0:
            heures_val = 0.0
        days.append(
            AiDayEntry(jour=jour, heures=heures_val, type=day_type, nature=nature)
        )
    days.sort(key=lambda d: (d.jour, d.nature))
    return days


def _build_proposal(
    *,
    year: int,
    month: int,
    source: str,
    extracted: Dict[str, Any],
    roster: List[RosterEmployee],
    default_nature: str,
) -> AiCalendarProposalResponse:
    num_days = cal_mod.monthrange(year, month)[1]
    employees_out: List[AiEmployeeProposal] = []
    for raw_emp in extracted.get("employees", []) or []:
        raw_name = str(raw_emp.get("name") or "").strip()
        if not raw_name:
            continue
        proposal = _resolve_employee(raw_name, roster)
        proposal.days = _coerce_days(
            raw_emp.get("days", []), num_days, default_nature
        )
        if not proposal.days:
            proposal.warnings.append("Aucun jour exploitable détecté pour cet employé.")
        employees_out.append(proposal)

    global_warnings = [str(w) for w in (extracted.get("warnings") or []) if str(w).strip()]
    if not employees_out:
        global_warnings.append(
            "Aucune donnée exploitable n'a été extraite. Reformulez ou vérifiez le document."
        )

    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=source,
        employees=employees_out,
        warnings=global_warnings,
    )


def parse_instruction(
    *,
    year: int,
    month: int,
    instruction: str,
    roster: List[RosterEmployee],
) -> AiCalendarProposalResponse:
    """Convertit une instruction en langage naturel en proposition de calendrier."""
    if not (instruction or "").strip():
        raise ScheduleAppError(
            "validation", "L'instruction est vide.", status_code=400
        )

    from app.modules.schedules.application.nl_fast_path import (
        try_fast_parse_instruction,
    )

    fast = try_fast_parse_instruction(
        year=year,
        month=month,
        instruction=instruction,
        roster=roster,
    )
    if fast is not None:
        return fast

    if not is_llm_configured():
        raise ScheduleAppError(
            "validation",
            "L'assistant IA n'est pas configuré sur ce serveur.",
            status_code=503,
        )

    roster_hint = _roster_hint_for_text(roster)
    user_prompt = (
        "Employés connus (pour orthographe des noms) :\n"
        f"{roster_hint or '(non fourni)'}\n\n"
        "Consigne RH :\n"
        f"{instruction.strip()}"
    )

    # Une instruction en langage naturel décrit le plus souvent ce qui a été fait ;
    # par défaut on retient « reel », mais l'IA bascule sur « prevu » si le libellé
    # parle de planning / prévisionnel.
    default_nature = "reel"
    result = extract_structured_json(
        system_prompt=_build_system_prompt(year, month, default_nature),
        user_prompt=user_prompt,
        json_schema=_PROPOSAL_JSON_SCHEMA,
        schema_name="schedule_fill",
        model=MODEL_SCHEDULE_NL_FILL,
        max_tokens=4096,
    )
    if result is None:
        raise ScheduleAppError(
            "error",
            "L'analyse de l'instruction a échoué. Reformulez et réessayez.",
            status_code=502,
        )

    return _build_proposal(
        year=year,
        month=month,
        source="texte",
        extracted=result.data,
        roster=roster,
        default_nature=default_nature,
    )


def extract_timesheet(
    *,
    year: int,
    month: int,
    file_content: bytes,
    filename: str,
    roster: List[RosterEmployee],
) -> AiCalendarProposalResponse:
    """Lit un relevé de pointeuse (PDF/image) et en extrait une proposition."""
    if not is_llm_configured():
        raise ScheduleAppError(
            "validation",
            "L'assistant IA n'est pas configuré sur ce serveur.",
            status_code=503,
        )

    try:
        text, method = extract_document_text(file_content, filename)
    except DocumentExtractionError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e

    if len(text) > _MAX_TIMESHEET_TEXT_CHARS:
        text = text[:_MAX_TIMESHEET_TEXT_CHARS] + "\n…(document tronqué)"

    filtered_roster = _roster_matching_document(text, roster)
    roster_hint = _roster_hint_for_text(filtered_roster, limit=40)
    user_prompt = (
        "Texte extrait d'un relevé de pointeuse (heures FAITES, nature='reel' "
        "sauf mention explicite de planning).\n\n"
        "Employés à rapprocher :\n"
        f"{roster_hint or '(non fourni)'}\n\n"
        "--- RELEVÉ ---\n"
        f"{text}"
    )

    # Un relevé de pointeuse est par nature un réalisé.
    default_nature = "reel"
    result = extract_structured_json(
        system_prompt=_build_system_prompt(year, month, default_nature),
        user_prompt=user_prompt,
        json_schema=_PROPOSAL_JSON_SCHEMA,
        schema_name="timesheet_extraction",
        model=MODEL_TIMESHEET_EXTRACTION,
        max_tokens=8192,
    )
    if result is None:
        raise ScheduleAppError(
            "error",
            "L'analyse du relevé a échoué. Vérifiez la lisibilité du document.",
            status_code=502,
        )

    return _build_proposal(
        year=year,
        month=month,
        source=f"relevé ({method})",
        extracted=result.data,
        roster=roster,
        default_nature=default_nature,
    )


__all__ = ["extract_timesheet", "parse_instruction"]
