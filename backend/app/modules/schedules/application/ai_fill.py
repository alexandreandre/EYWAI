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


def _build_system_prompt(
    year: int,
    month: int,
    default_nature: str,
    single_employee_name: str | None = None,
    collective: bool = False,
) -> str:
    num_days = cal_mod.monthrange(year, month)[1]
    base = (
        "Assistant RH : convertis une consigne d'heures en JSON pour un calendrier "
        "de paie mensuel français.\n"
        f"Période : {month}/{year}. {_month_calendar_anchor(year, month)}\n\n"
        "Champs par jour : jour (1-" + str(num_days) + "), heures (nombre ou null), "
        "type (travail|conge|ferie|arret_maladie|absence|weekend), "
        "nature (prevu|reel).\n"
        "- prevu = heures planifiées ; reel = heures faites / pointage.\n"
        f"- Par défaut nature='{default_nature}' si non précisé.\n"
        "- Même date peut avoir prevu et reel si la consigne le distingue.\n"
        "- Ne crée aucun jour non mentionné.\n"
    )
    if single_employee_name:
        return base + (
            "- IMPORTANT : la consigne concerne UN SEUL salarié : "
            f"{single_employee_name}.\n"
            "- Attribue 100% des heures à ce salarié, même si aucun nom n'est écrit.\n"
            f"- Renseigne toujours name='{single_employee_name}' (un seul employé en sortie).\n"
            "- warnings : ambiguïtés (heures, nature)."
        )
    if collective:
        return base + (
            "- IMPORTANT : la consigne décrit un horaire COMMUN à plusieurs "
            "salariés (saisie collective).\n"
            "- Ne cherche PAS à identifier des noms : aucun nom n'est attendu.\n"
            "- Produis UN SEUL employé en sortie, name='(tous)', contenant "
            "l'ensemble des jours décrits.\n"
            "- N'invente aucun jour non mentionné.\n"
            "- warnings : ambiguïtés (heures, nature)."
        )
    return base + (
        "- Ne crée aucun employé non mentionné.\n"
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


def _build_single_employee_proposal(
    *,
    year: int,
    month: int,
    source: str,
    extracted: Dict[str, Any],
    target: RosterEmployee,
    default_nature: str,
) -> AiCalendarProposalResponse:
    """Force l'attribution de toutes les heures détectées à un unique employé.

    Utilisé depuis la fiche collaborateur : quelle que soit la façon dont l'IA a
    nommé (ou non) la personne, on rattache l'ensemble des jours au salarié ciblé.
    """
    num_days = cal_mod.monthrange(year, month)[1]
    raw_days: List[Dict[str, Any]] = []
    for raw_emp in extracted.get("employees", []) or []:
        raw_days.extend(raw_emp.get("days", []) or [])

    days = _coerce_days(raw_days, num_days, default_nature)
    full_name = f"{target.first_name} {target.last_name}"
    global_warnings = [
        str(w) for w in (extracted.get("warnings") or []) if str(w).strip()
    ]

    if not days:
        global_warnings.append(
            "Aucune donnée exploitable n'a été extraite. Reformulez ou vérifiez le document."
        )
        return AiCalendarProposalResponse(
            year=year,
            month=month,
            source=source,
            employees=[],
            warnings=global_warnings,
        )

    proposal = AiEmployeeProposal(
        raw_name=full_name,
        employee_id=target.id,
        matched_name=full_name,
        match_confidence="high",
        days=days,
    )
    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=source,
        employees=[proposal],
        warnings=global_warnings,
    )


def _build_broadcast_proposal(
    *,
    year: int,
    month: int,
    source: str,
    extracted: Dict[str, Any],
    roster: List[RosterEmployee],
    default_nature: str,
) -> AiCalendarProposalResponse:
    """Applique un même jeu de jours à TOUS les employés du roster.

    Mode « saisie collective » : la consigne ne cite aucun nom et concerne
    l'ensemble des collaborateurs ciblés (ex. les « À saisir »). Le RH peut
    ensuite ajuster chaque collaborateur individuellement avant enregistrement.
    """
    num_days = cal_mod.monthrange(year, month)[1]
    raw_days: List[Dict[str, Any]] = []
    for raw_emp in extracted.get("employees", []) or []:
        raw_days.extend(raw_emp.get("days", []) or [])

    days = _coerce_days(raw_days, num_days, default_nature)
    global_warnings = [
        str(w) for w in (extracted.get("warnings") or []) if str(w).strip()
    ]

    if not days or not roster:
        global_warnings.append(
            "Aucune donnée exploitable n'a été extraite. Reformulez la consigne."
        )
        return AiCalendarProposalResponse(
            year=year,
            month=month,
            source=source,
            employees=[],
            warnings=global_warnings,
        )

    employees_out: List[AiEmployeeProposal] = []
    for emp in roster:
        full_name = f"{emp.first_name} {emp.last_name}"
        employees_out.append(
            AiEmployeeProposal(
                raw_name=full_name,
                employee_id=emp.id,
                matched_name=full_name,
                match_confidence="high",
                days=[
                    AiDayEntry(
                        jour=d.jour,
                        heures=d.heures,
                        type=d.type,
                        nature=d.nature,
                    )
                    for d in days
                ],
            )
        )

    if len(employees_out) > 1:
        global_warnings.insert(
            0,
            f"Saisie collective appliquée à {len(employees_out)} collaborateur(s). "
            "Ajustez individuellement si besoin avant d'enregistrer.",
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
    single_employee: bool = False,
    broadcast: bool = False,
) -> AiCalendarProposalResponse:
    """Convertit une instruction en langage naturel en proposition de calendrier.

    Si `single_employee` est vrai, toutes les heures sont rattachées à l'unique
    employé du roster (mode fiche collaborateur), même sans nom dans la consigne.

    Si `broadcast` est vrai ou si la consigne vise « tout le monde », un même
    jeu de jours est appliqué à tous les employés du roster (hors exclusions « sauf »).
    """
    if not (instruction or "").strip():
        raise ScheduleAppError(
            "validation", "L'instruction est vide.", status_code=400
        )

    from app.modules.schedules.application.nl_fast_path import (
        excluded_employees_from_instruction,
        is_broadcast_instruction,
        try_fast_parse_instruction,
    )

    target = roster[0] if (single_employee and roster) else None
    broadcast_mode = bool(broadcast or is_broadcast_instruction(instruction))
    collective = broadcast_mode and target is None and bool(roster)
    excluded = (
        excluded_employees_from_instruction(instruction, roster) if collective else []
    )
    excluded_ids = {e.id for e in excluded}
    target_roster = [e for e in roster if e.id not in excluded_ids]

    # En mode mono-employé, on saute le fast-path (résolution par nom) pour
    # garantir l'attribution à la bonne personne via le LLM puis le forçage.
    # En mode collectif, on force la diffusion à tout le roster ciblé.
    if target is None:
        fast = try_fast_parse_instruction(
            year=year,
            month=month,
            instruction=instruction,
            roster=target_roster if collective else roster,
            force_broadcast=collective,
        )
        if fast is not None:
            return fast

    if not is_llm_configured():
        raise ScheduleAppError(
            "validation",
            "L'assistant IA n'est pas configuré sur ce serveur.",
            status_code=503,
        )

    if target is not None:
        user_prompt = (
            f"La consigne concerne uniquement le salarié : {target.first_name} "
            f"{target.last_name}.\n\n"
            "Consigne RH :\n"
            f"{instruction.strip()}"
        )
        system_prompt_name = f"{target.first_name} {target.last_name}"
    elif collective:
        user_prompt = (
            "Consigne RH (horaire commun à plusieurs salariés) :\n"
            f"{instruction.strip()}\n\n"
            "Produis un seul bloc de jours communs (name='(tous)')."
        )
        if excluded:
            names = ", ".join(f"{e.first_name} {e.last_name}" for e in excluded)
            user_prompt += f"\nExclure explicitement : {names}."
        system_prompt_name = None
    else:
        roster_hint = _roster_hint_for_text(roster)
        user_prompt = (
            "Employés connus (pour orthographe des noms) :\n"
            f"{roster_hint or '(non fourni)'}\n\n"
            "Consigne RH :\n"
            f"{instruction.strip()}"
        )
        system_prompt_name = None

    # Une instruction en langage naturel décrit le plus souvent ce qui a été fait ;
    # par défaut on retient « reel », mais l'IA bascule sur « prevu » si le libellé
    # parle de planning / prévisionnel.
    default_nature = "reel"
    result = extract_structured_json(
        system_prompt=_build_system_prompt(
            year, month, default_nature, system_prompt_name, collective=collective
        ),
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

    if target is not None:
        return _build_single_employee_proposal(
            year=year,
            month=month,
            source="texte",
            extracted=result.data,
            target=target,
            default_nature=default_nature,
        )

    if collective:
        return _build_broadcast_proposal(
            year=year,
            month=month,
            source="texte (saisie collective)",
            extracted=result.data,
            roster=target_roster,
            default_nature=default_nature,
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
    single_employee: bool = False,
) -> AiCalendarProposalResponse:
    """Lit un relevé de pointeuse (PDF/image) et en extrait une proposition.

    Si `single_employee` est vrai, toutes les heures lues sont rattachées à
    l'unique employé du roster (mode fiche collaborateur).
    """
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

    target = roster[0] if (single_employee and roster) else None

    if target is not None:
        full_name = f"{target.first_name} {target.last_name}"
        user_prompt = (
            "Texte extrait d'un relevé de pointeuse (heures FAITES, nature='reel' "
            "sauf mention explicite de planning).\n\n"
            f"Le relevé concerne uniquement le salarié : {full_name}.\n"
            "Attribue toutes les heures à ce salarié.\n\n"
            "--- RELEVÉ ---\n"
            f"{text}"
        )
        system_prompt_name = full_name
    else:
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
        system_prompt_name = None

    # Un relevé de pointeuse est par nature un réalisé.
    default_nature = "reel"
    result = extract_structured_json(
        system_prompt=_build_system_prompt(
            year, month, default_nature, system_prompt_name
        ),
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

    if target is not None:
        return _build_single_employee_proposal(
            year=year,
            month=month,
            source=f"relevé ({method})",
            extracted=result.data,
            target=target,
            default_nature=default_nature,
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
