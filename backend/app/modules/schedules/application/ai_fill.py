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


def _month_calendar_hint(year: int, month: int) -> str:
    """Décrit chaque jour du mois (numéro -> jour de semaine) pour guider le LLM."""
    num_days = cal_mod.monthrange(year, month)[1]
    lines = []
    for day in range(1, num_days + 1):
        weekday = _WEEKDAYS_FR[cal_mod.weekday(year, month, day)]
        lines.append(f"{day}={weekday}")
    return ", ".join(lines)


def _build_system_prompt(year: int, month: int, default_nature: str) -> str:
    num_days = cal_mod.monthrange(year, month)[1]
    default_label = (
        "heures prévues (prevu)" if default_nature == "prevu" else "heures faites (reel)"
    )
    return (
        "Tu es un assistant RH qui convertit une saisie d'heures de travail en "
        "données structurées pour un calendrier de paie mensuel français.\n"
        f"Période : mois {month}, année {year} ({num_days} jours).\n"
        f"Correspondance jour du mois -> jour de la semaine : {_month_calendar_hint(year, month)}.\n\n"
        "Règles :\n"
        "- Pour chaque employé mentionné, retourne la liste des jours concernés avec "
        "le nombre d'heures (heures), un type et une nature.\n"
        "- type doit valoir l'une de ces valeurs : travail, conge, ferie, "
        "arret_maladie, absence, weekend.\n"
        "- Pour un jour travaillé, type=travail et heures = nombre d'heures "
        "(ex: 7, 8, 7.5). Pour un repos/absence, heures=0 ou null avec le type adapté.\n\n"
        "DISTINCTION IMPORTANTE — nature des heures (champ nature) :\n"
        "- nature='prevu' = heures PRÉVUES / planifiées (planning prévisionnel, "
        "ce qui est PLANIFIÉ ou À FAIRE). Indices : « prévu », « prévoit », "
        "« planning », « doit faire », « est censé », « théorique », « contrat », au futur.\n"
        "- nature='reel' = heures FAITES / réalisées (ce qui a EFFECTIVEMENT été "
        "travaillé). Indices : « a fait », « a travaillé », « réalisé », « pointage », "
        "« relevé de pointeuse », « effectué », au passé.\n"
        f"- En l'absence d'indication claire, utilise nature='{default_nature}' "
        f"({default_label}) par défaut.\n"
        "- Une même demande peut mélanger les deux (ex: « prévu 8h mais n'a fait que 6h ») : "
        "produis alors deux jours distincts avec la même date et une nature différente.\n"
        "- Si la nature est ambiguë, choisis la valeur par défaut et ajoute un warning.\n\n"
        "- N'invente jamais de jour ou d'employé non mentionné. Ne déduis pas de jours "
        "implicites au-delà de ce qui est demandé.\n"
        f"- jour est le numéro du jour dans le mois (1 à {num_days}).\n"
        "- Recopie le nom de l'employé exactement comme écrit dans la source, dans le champ name.\n"
        "- Mets dans warnings toute ambiguïté (employé non identifiable, heures illisibles, "
        "nature prévu/fait incertaine, etc.)."
    )


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
    if not is_llm_configured():
        raise ScheduleAppError(
            "validation",
            "L'assistant IA n'est pas configuré sur ce serveur.",
            status_code=503,
        )
    if not (instruction or "").strip():
        raise ScheduleAppError(
            "validation", "L'instruction est vide.", status_code=400
        )

    roster_hint = "; ".join(
        f"{e.first_name} {e.last_name}" for e in roster[:200]
    )
    user_prompt = (
        "Employés de l'entreprise (utilise ces noms pour identifier qui est concerné) :\n"
        f"{roster_hint or '(non fourni)'}\n\n"
        "Détermine pour chaque jour s'il s'agit d'heures prévues ou faites (champ nature).\n\n"
        "Instruction du RH :\n"
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

    roster_hint = "; ".join(f"{e.first_name} {e.last_name}" for e in roster[:200])
    user_prompt = (
        "Voici le texte brut extrait d'un relevé de pointeuse (peut contenir "
        "plusieurs employés et un tableau jours x heures).\n"
        "Un relevé de pointeuse décrit des heures FAITES (nature='reel'), sauf si le "
        "document indique explicitement qu'il s'agit d'un planning prévisionnel "
        "(nature='prevu').\n\n"
        "Employés connus de l'entreprise (pour rapprochement des noms) :\n"
        f"{roster_hint or '(non fourni)'}\n\n"
        "--- TEXTE DU RELEVÉ ---\n"
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
