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
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AffectedMonth,
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
from app.modules.schedules.application.timesheet_native_extract import (
    extract_timesheet_native as _native_extractor,
)
from app.shared.infrastructure.documents.text_extraction import (
    extract_pdf_text_layer,
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


def _build_timesheet_system_prompt(
    year: int,
    month: int,
    default_nature: str,
    single_employee_name: str | None = None,
    period_context: str = "",
    week_anchor_context: str = "",
) -> str:
    """Prompt spécialisé relevé de pointeuse (hebdo ou mensuel partiel)."""
    base = _build_system_prompt(
        year, month, default_nature, single_employee_name
    )
    extra = (
        "\n\nRELEVÉ DE POINTEUSE — règles additionnelles :\n"
        "- Le document peut couvrir une semaine seule ou une partie du mois.\n"
        "- N'extraire que les jours effectivement présents dans le relevé.\n"
        "- Priorité absolue aux dates explicites (JJ/MM, JJ/MM/AAAA) pour "
        "déterminer le champ `jour` du mois cible.\n"
        "- Ne pas mapper les colonnes Lun–Mar–Mer sur les jours 1–2–3 du mois "
        "sauf si aucune date n'est lisible et qu'un ancrage hebdomadaire est fourni.\n"
        "- Si la période du relevé ne correspond pas au mois cible, l'indiquer "
        "dans warnings (en français).\n"
        "- Tous les messages warnings en français.\n"
        "- Ne pas alerter pour les salariés absents du relevé (hors document).\n"
        "- Jour férié sans pointage → type ferie (pas absence).\n"
    )
    if period_context:
        extra += f"\n{period_context}\n"
    if week_anchor_context:
        extra += f"\n{week_anchor_context}\n"
    return base + extra


def _filter_timesheet_warnings(
    warnings: List[str], document_text: str = ""
) -> List[str]:
    """Supprime le bruit LLM (alertes techniques, commentaires PDF, salariés hors relevé)."""
    from app.modules.schedules.application.timesheet_warning_filter import (
        filter_timesheet_warnings,
    )

    _ = document_text
    return filter_timesheet_warnings(warnings)


def _compute_affected_months_from_period(
    *,
    year: int,
    month: int,
    period_start: date | None,
    period_end: date | None,
    employees: List[AiEmployeeProposal],
) -> List[AffectedMonth]:
    """Mois touchés par le relevé (semaine à cheval sur 2 mois)."""
    months_map: Dict[Tuple[int, int], set[int]] = {}
    if period_start and period_end:
        current = period_start
        while current <= period_end:
            key = (current.year, current.month)
            months_map.setdefault(key, set()).add(current.day)
            current += timedelta(days=1)
    target_days = {d.jour for emp in employees for d in emp.days}
    if target_days:
        months_map[(year, month)] = months_map.get((year, month), set()) | target_days
    return [
        AffectedMonth(year=y, month=m, days=sorted(days))
        for (y, m), days in sorted(months_map.items())
    ]


def _compute_review_summary(
    employees: List[AiEmployeeProposal],
) -> dict[str, int]:
    ready = warning = error = empty = incomplete = gap = 0
    for emp in employees:
        if emp.review_status == "empty":
            empty += 1
        elif emp.review_status == "error" or not emp.employee_id:
            error += 1
        elif emp.quality_issue == "extraction_incomplete":
            incomplete += 1
        elif emp.quality_issue == "weekly_total_gap":
            gap += 1
        elif emp.review_status == "warning" or emp.match_confidence == "medium":
            warning += 1
        else:
            ready += 1
    return {
        "ready": ready,
        "warning": warning,
        "error": error,
        "empty": empty,
        "incomplete": incomplete,
        "gap": gap,
        "total": len(employees),
    }


def _build_proposal_from_cegid(
    *,
    year: int,
    month: int,
    source: str,
    parse_result,
    roster: List[RosterEmployee],
    default_nature: str,
) -> AiCalendarProposalResponse:
    from app.modules.schedules.application.employee_match import (
        resolve_employee_for_timesheet,
    )

    employees_out: List[AiEmployeeProposal] = []
    for block in parse_result.employees:
        proposal = resolve_employee_for_timesheet(
            raw_name=block.raw_name,
            matricule=block.matricule,
            roster=roster,
        )
        if block.empty_week:
            proposal.review_status = "empty"
        days: List[AiDayEntry] = []
        for d in block.days:
            days.append(
                AiDayEntry(
                    jour=d.jour,
                    heures=d.heures,
                    type="travail",
                    nature=default_nature,
                    year=d.year if (d.year, d.month) != (year, month) else None,
                    month=d.month if (d.year, d.month) != (year, month) else None,
                )
            )
        proposal.days = days
        proposal.weekly_total_pdf = block.weekly_total_hours
        proposal.days_expected_count = block.days_expected_count
        proposal.days_imported_count = block.days_parsed_count
        proposal.coverage_ratio = block.coverage_ratio
        if block.parse_warnings:
            proposal.warnings.extend(block.parse_warnings)
        if not days and not block.empty_week:
            proposal.warnings.append("Aucun jour exploitable détecté pour cet employé.")
        employees_out.append(proposal)

    global_warnings = list(parse_result.parse_warnings)
    if not employees_out:
        global_warnings.append(
            "Aucune donnée exploitable n'a été extraite du relevé Cegid."
        )

    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=source,
        employees=employees_out,
        warnings=global_warnings,
        detected_format="cegid_weekly",
        parse_confidence=parse_result.confidence,
    )


def _build_single_employee_from_cegid(
    *,
    year: int,
    month: int,
    source: str,
    parse_result,
    target: RosterEmployee,
    default_nature: str,
) -> AiCalendarProposalResponse:
    """Fast path Cegid pour import fiche collaborateur (un seul bloc PDF)."""
    block = parse_result.employees[0]
    full_name = f"{target.first_name} {target.last_name}"
    days: List[AiDayEntry] = [
        AiDayEntry(
            jour=d.jour,
            heures=d.heures,
            type="travail",
            nature=default_nature,
            year=d.year if (d.year, d.month) != (year, month) else None,
            month=d.month if (d.year, d.month) != (year, month) else None,
        )
        for d in block.days
    ]
    proposal = AiEmployeeProposal(
        raw_name=full_name,
        employee_id=target.id,
        matched_name=full_name,
        match_confidence="high",
        match_method="matricule" if block.matricule else "name_exact",
        time_tracking_id=block.matricule or target.time_tracking_id,
        days=days,
        weekly_total_pdf=block.weekly_total_hours,
        days_expected_count=block.days_expected_count,
        days_imported_count=block.days_parsed_count,
        coverage_ratio=block.coverage_ratio,
    )
    if block.empty_week:
        proposal.review_status = "empty"
    if block.parse_warnings:
        proposal.warnings.extend(block.parse_warnings)
    return AiCalendarProposalResponse(
        year=year,
        month=month,
        source=source,
        employees=[proposal],
        warnings=list(parse_result.parse_warnings),
        detected_format="cegid_weekly",
        parse_confidence=parse_result.confidence,
    )


def _finalize_timesheet_proposal(
    response: AiCalendarProposalResponse,
    *,
    roster: List[RosterEmployee],
    company_id: str | None,
    period_detection,
    month_auto_corrected: bool = False,
    requested_year: int | None = None,
    requested_month: int | None = None,
    month_correction_message: str | None = None,
    detected_format: str | None = None,
    parse_confidence: float | None = None,
    extraction_method: str | None = None,
    extraction_warnings: List[str] | None = None,
    extraction_pages_total: int | None = None,
    extraction_pages_processed: int | None = None,
    extraction_truncated: bool = False,
) -> AiCalendarProposalResponse:
    from app.modules.schedules.application.parsers.cegid_weekly import (
        focus_week_index_for_period,
    )
    from app.modules.schedules.application.timesheet_enrichment import (
        enrich_proposal_employees,
    )
    from app.modules.schedules.application.timesheet_quality import run_quality_checks

    fmt = detected_format or response.detected_format
    conf = parse_confidence if parse_confidence is not None else response.parse_confidence

    if company_id:
        from app.modules.schedules.application.punch_accounting_service import (
            apply_punch_accounting_to_proposal,
            punch_calc_fingerprint,
        )
        from app.modules.schedules.infrastructure import punch_accounting_repository

        if punch_accounting_repository.get_settings(company_id).enabled:
            response = apply_punch_accounting_to_proposal(response, company_id)
        response.calc_fingerprint = punch_calc_fingerprint(company_id)

    enriched = enrich_proposal_employees(
        response.employees,
        year=response.year,
        month=response.month,
        company_id=company_id,
    )
    enriched, quality_checks, roster_not_in_doc = run_quality_checks(
        enriched,
        roster,
        parse_confidence=conf,
        detected_format=fmt,
    )

    response = response.model_copy(
        update={
            "employees": enriched,
            "quality_checks": quality_checks,
            "roster_not_in_document_count": roster_not_in_doc,
            "review_summary": _compute_review_summary(enriched),
            "warnings": _filter_timesheet_warnings(
                list(response.warnings) + (extraction_warnings or [])
            ),
            "extraction_method": extraction_method,
            "extraction_warnings": extraction_warnings or [],
            "extraction_pages_total": extraction_pages_total,
            "extraction_pages_processed": extraction_pages_processed,
            "extraction_truncated": extraction_truncated,
        }
    )

    if period_detection.start_date and period_detection.end_date:
        span = (period_detection.end_date - period_detection.start_date).days + 1
        if span <= 10 and (
            period_detection.start_date.month != period_detection.end_date.month
            or period_detection.start_date.year != period_detection.end_date.year
        ):
            response = response.model_copy(
                update={
                    "affected_months": _compute_affected_months_from_period(
                        year=response.year,
                        month=response.month,
                        period_start=period_detection.start_date,
                        period_end=period_detection.end_date,
                        employees=enriched,
                    )
                }
            )

    focus_idx = focus_week_index_for_period(
        response.year,
        response.month,
        period_detection.start_date,
    )
    if focus_idx is not None:
        response = response.model_copy(update={"focus_week_index": focus_idx})

    return _attach_period_metadata(
        response,
        period_detection,
        month_auto_corrected=month_auto_corrected,
        requested_year=requested_year,
        requested_month=requested_month,
        month_correction_message=month_correction_message,
    )


def _attach_period_metadata(
    response: AiCalendarProposalResponse,
    detection,
    *,
    month_auto_corrected: bool = False,
    requested_year: int | None = None,
    requested_month: int | None = None,
    month_correction_message: str | None = None,
) -> AiCalendarProposalResponse:
    from app.modules.schedules.application.timesheet_period import (
        suggested_target_month,
    )

    days_count = sum(len(emp.days) for emp in response.employees)
    suggested = suggested_target_month(detection)
    merged_warnings = list(response.warnings)
    for w in detection.warnings:
        if w not in merged_warnings:
            merged_warnings.append(w)

    period_warnings = list(detection.warnings)
    if month_auto_corrected and month_correction_message:
        period_warnings = [month_correction_message]

    return response.model_copy(
        update={
            "detected_scope": detection.scope,
            "detected_period_start": detection.start_date,
            "detected_period_end": detection.end_date,
            "period_confidence": detection.confidence,
            "period_warnings": period_warnings,
            "detected_days_count": days_count,
            "warnings": merged_warnings,
            "suggested_year": suggested[0] if suggested else None,
            "suggested_month": suggested[1] if suggested else None,
            "month_auto_corrected": month_auto_corrected,
            "requested_year": requested_year,
            "requested_month": requested_month,
            "month_correction_message": month_correction_message,
        }
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


_MAX_LLM_TEXT_CHARS = 14_000
_CEGID_CONFIDENCE_THRESHOLD = 0.75


def _resolve_employee_from_match(
    raw_name: str, roster: List[RosterEmployee]
) -> AiEmployeeProposal:
    from app.modules.schedules.application.employee_match import (
        resolve_employee_for_timesheet,
    )

    return resolve_employee_for_timesheet(
        raw_name=raw_name, matricule=None, roster=roster
    )


def _resolve_employee(raw_name: str, roster: List[RosterEmployee]) -> AiEmployeeProposal:
    """Associe un nom brut à un employé du roster (matching déterministe)."""
    return _resolve_employee_from_match(raw_name, roster)


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
        proposal = _resolve_employee_from_match(raw_name, roster)
        proposal.days = _coerce_days(
            raw_emp.get("days", []), num_days, default_nature
        )
        if not proposal.days:
            proposal.warnings.append("Aucun jour exploitable détecté pour cet employé.")
        employees_out.append(proposal)

    global_warnings = _filter_timesheet_warnings(
        [str(w) for w in (extracted.get("warnings") or []) if str(w).strip()]
    )
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
        try_mirror_planned_instruction,
    )

    target = roster[0] if (single_employee and roster) else None
    broadcast_mode = bool(broadcast or is_broadcast_instruction(instruction))
    collective = broadcast_mode and target is None and bool(roster)
    excluded = (
        excluded_employees_from_instruction(instruction, roster) if collective else []
    )
    excluded_ids = {e.id for e in excluded}
    target_roster = [e for e in roster if e.id not in excluded_ids]

    mirror = try_mirror_planned_instruction(
        year=year,
        month=month,
        instruction=instruction,
        roster=target_roster if collective else roster,
        target=target,
        force_broadcast=collective,
    )
    if mirror is not None:
        return mirror

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
        timeout=60.0,
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


def _extract_timesheet_hybrid_path(
    *,
    year: int,
    month: int,
    file_content: bytes,
    filename: str,
    roster: List[RosterEmployee],
    single_employee: bool,
    document_scope: str,
    week_anchor_date: date | None,
    company_id: str | None,
    user_id: str | None,
    import_job_id: str | None,
    on_progress: Any | None,
    skip_audit: bool,
    mode: str = "hybrid",
) -> AiCalendarProposalResponse:
    from app.modules.schedules.application.schedule_import_audit import (
        record_schedule_import_run,
    )
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        extract_timesheet_hybrid,
    )
    from app.modules.schedules.application.timesheet_period import (
        align_period_warnings,
        detect_timesheet_period,
        format_week_anchor_context,
        resolve_effective_target_month,
    )
    from app.shared.infrastructure.documents import (
        DocumentExtractionError,
        extract_document_text,
    )

    scope_input = document_scope if document_scope in ("auto", "weekly", "monthly") else "auto"
    requested_year, requested_month = year, month

    # Pré-scan OCR : détecter le mois réel avant l'extraction hybride (vision + LLM),
    # sinon les jours sont mappés sur le mois affiché dans le calendrier RH.
    if mode == "native":
        # Jamais d'OCR en natif : couche texte PDF seule, pré-scan sauté sinon.
        preview_text = extract_pdf_text_layer(file_content)
    else:
        try:
            preview_text, _, _ = extract_document_text(file_content, filename)
        except DocumentExtractionError as e:
            raise ScheduleAppError("validation", str(e), status_code=400) from e

    period_detection = detect_timesheet_period(
        preview_text,
        target_year=requested_year,
        target_month=requested_month,
        document_scope=scope_input,
    )
    eff_year, eff_month, month_auto_corrected, correction_msg = (
        resolve_effective_target_month(
            period_detection, requested_year, requested_month
        )
    )
    if month_auto_corrected:
        year, month = eff_year, eff_month
        align_period_warnings(period_detection, year, month)

    known_mats = [
        e.time_tracking_id for e in roster if (e.time_tracking_id or "").strip()
    ]
    week_anchor_context = ""
    if week_anchor_date is not None:
        week_anchor_context = format_week_anchor_context(
            week_anchor_date, year, month
        )
    # Feuilles manuscrites : la pause déduite suit le paramétrage de la société,
    # comme sur une journée badgée, plutôt qu'un forfait figé dans le code.
    punch_settings = None
    if company_id:
        from app.modules.schedules.infrastructure import punch_accounting_repository

        punch_settings = punch_accounting_repository.get_settings(company_id)

    try:
        extractor = _native_extractor if mode == "native" else extract_timesheet_hybrid
        hybrid = extractor(
            file_content=file_content,
            filename=filename,
            year=year,
            month=month,
            known_matricules=known_mats,
            on_progress=on_progress,
            week_anchor_context=week_anchor_context,
            week_anchor_date=week_anchor_date,
            punch_settings=punch_settings,
        )
    except DocumentExtractionError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e

    text = hybrid.full_ocr_text
    method = hybrid.extraction_method
    extraction_warnings = list(hybrid.warnings)

    parse_result = hybrid.parse_result
    if parse_result.format_detected and parse_result.confidence >= 0.5:
        period_detection.scope = "weekly"
        if parse_result.period_start:
            period_detection.start_date = parse_result.period_start
        if parse_result.period_end:
            period_detection.end_date = parse_result.period_end
        if parse_result.confidence >= _CEGID_CONFIDENCE_THRESHOLD:
            period_detection.confidence = "high"
        align_period_warnings(period_detection, year, month)

    if (
        week_anchor_date is not None
        and period_detection.start_date is None
        and period_detection.end_date is None
    ):
        period_detection.scope = "weekly"
        period_detection.start_date = week_anchor_date
        period_detection.end_date = week_anchor_date + timedelta(days=6)

    default_nature = "reel"
    detected_format = "hybrid_vision_ocr"
    if hybrid.used_cegid_fallback:
        detected_format = hybrid.fallback_parser_key or "cegid_weekly"

    source_label = (
        f"relevé IA hybride ({method})"
        if not hybrid.used_cegid_fallback
        else f"relevé Cegid repli ({method})"
    )

    use_single = (
        single_employee
        and parse_result.employees
        and len(parse_result.employees) == 1
        and roster
    )
    if use_single:
        response = _build_single_employee_from_cegid(
            year=year,
            month=month,
            source=source_label,
            parse_result=parse_result,
            target=roster[0],
            default_nature=default_nature,
        )
    else:
        response = _build_proposal_from_cegid(
            year=year,
            month=month,
            source=source_label,
            parse_result=parse_result,
            roster=roster,
            default_nature=default_nature,
        )
        response = response.model_copy(update={"detected_format": detected_format})

    final = _finalize_timesheet_proposal(
        response,
        roster=roster,
        company_id=company_id,
        period_detection=period_detection,
        month_auto_corrected=month_auto_corrected,
        requested_year=requested_year if month_auto_corrected else None,
        requested_month=requested_month if month_auto_corrected else None,
        month_correction_message=correction_msg,
        detected_format=detected_format,
        parse_confidence=parse_result.confidence,
        extraction_method=method,
        extraction_warnings=extraction_warnings,
        extraction_pages_total=hybrid.pages_total or None,
        extraction_pages_processed=hybrid.pages_processed or None,
        extraction_truncated=hybrid.truncated,
    )
    final = final.model_copy(
        update={
            "extraction_mode": mode,
            "consensus_conflicts": hybrid.consensus_conflicts,
        }
    )

    if company_id and not skip_audit:
        record_schedule_import_run(
            company_id=company_id,
            user_id=user_id,
            filename=filename,
            proposal=final,
            file_content=file_content,
            extraction_method=method,
            raw_ocr_text=text,
            import_job_id=import_job_id,
            extraction_mode=mode,
            page_count=hybrid.pages_processed,
            consensus_conflicts=hybrid.consensus_conflicts,
        )

    return final


def extract_timesheet(
    *,
    year: int,
    month: int,
    file_content: bytes,
    filename: str,
    roster: List[RosterEmployee],
    single_employee: bool = False,
    document_scope: str = "auto",
    week_anchor_date: date | None = None,
    company_id: str | None = None,
    user_id: str | None = None,
    import_job_id: str | None = None,
    on_progress: Any | None = None,
    skip_audit: bool = False,
) -> AiCalendarProposalResponse:
    """Lit un relevé de pointeuse (PDF/image) et en extrait une proposition."""
    from app.modules.schedules.application.timesheet_import.registry import (
        best_deterministic_parse,
    )
    from app.modules.schedules.application.roster_enrichment import (
        enrich_roster_time_tracking_ids,
    )
    from app.modules.schedules.application.schedule_import_audit import (
        record_schedule_import_run,
    )
    from app.modules.schedules.application.timesheet_extract_config import (
        timesheet_extract_mode,
    )
    from app.modules.schedules.application.timesheet_period import (
        align_period_warnings,
        detect_timesheet_period,
        format_period_context,
        format_week_anchor_context,
        resolve_effective_target_month,
    )

    extract_mode = timesheet_extract_mode()
    roster = enrich_roster_time_tracking_ids(roster, company_id)

    if extract_mode in ("hybrid", "native"):
        return _extract_timesheet_hybrid_path(
            mode=extract_mode,
            year=year,
            month=month,
            file_content=file_content,
            filename=filename,
            roster=roster,
            single_employee=single_employee,
            document_scope=document_scope,
            week_anchor_date=week_anchor_date,
            company_id=company_id,
            user_id=user_id,
            import_job_id=import_job_id,
            on_progress=on_progress,
            skip_audit=skip_audit,
        )

    try:
        text, method, extraction_meta = extract_document_text(file_content, filename)
    except DocumentExtractionError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e

    extraction_warnings = list(extraction_meta.warnings)

    scope_input = document_scope if document_scope in ("auto", "weekly", "monthly") else "auto"
    requested_year, requested_month = year, month
    period_detection = detect_timesheet_period(
        text,
        target_year=requested_year,
        target_month=requested_month,
        document_scope=scope_input,
    )
    eff_year, eff_month, month_auto_corrected, correction_msg = (
        resolve_effective_target_month(
            period_detection, requested_year, requested_month
        )
    )
    if month_auto_corrected:
        year, month = eff_year, eff_month
        align_period_warnings(period_detection, year, month)

    deterministic = best_deterministic_parse(text, year=year, month=month)
    cegid_result = deterministic.parse_result
    detected_parser = deterministic.parser_key
    use_cegid = (
        cegid_result
        and cegid_result.format_detected
        and cegid_result.confidence >= _CEGID_CONFIDENCE_THRESHOLD
        and cegid_result.employees
    )
    use_cegid_single = (
        single_employee
        and cegid_result
        and cegid_result.format_detected
        and cegid_result.confidence >= 0.5
        and len(cegid_result.employees) == 1
        and roster
    )

    if cegid_result and cegid_result.format_detected and cegid_result.confidence >= 0.5:
        period_detection.scope = "weekly"
        if cegid_result.period_start:
            period_detection.start_date = cegid_result.period_start
        if cegid_result.period_end:
            period_detection.end_date = cegid_result.period_end
        if cegid_result.confidence >= _CEGID_CONFIDENCE_THRESHOLD:
            period_detection.confidence = "high"

    default_nature = "reel"
    detected_format: str | None = None
    parse_confidence: float | None = None

    if (use_cegid and not single_employee) or use_cegid_single:
        if use_cegid_single:
            response = _build_single_employee_from_cegid(
                year=year,
                month=month,
                source=f"relevé Cegid ({method})",
                parse_result=cegid_result,
                target=roster[0],
                default_nature=default_nature,
            )
        else:
            response = _build_proposal_from_cegid(
                year=year,
                month=month,
                source=f"relevé Cegid ({method})",
                parse_result=cegid_result,
                roster=roster,
                default_nature=default_nature,
            )
        detected_format = detected_parser or "cegid_weekly"
        parse_confidence = cegid_result.confidence
    else:
        if not is_llm_configured():
            if cegid_result.format_detected and cegid_result.employees:
                response = _build_proposal_from_cegid(
                    year=year,
                    month=month,
                    source=f"relevé Cegid ({method})",
                    parse_result=cegid_result,
                    roster=roster,
                    default_nature=default_nature,
                )
                detected_format = detected_parser or "cegid_weekly"
                parse_confidence = cegid_result.confidence
            else:
                raise ScheduleAppError(
                    "validation",
                    "L'assistant IA n'est pas configuré sur ce serveur.",
                    status_code=503,
                )
        else:
            llm_text = text
            if len(llm_text) > _MAX_LLM_TEXT_CHARS:
                llm_text = llm_text[:_MAX_LLM_TEXT_CHARS] + "\n…(document tronqué)"
                extraction_meta.truncated = True
                extraction_warnings.append(
                    f"Document tronqué à {_MAX_LLM_TEXT_CHARS} caractères "
                    "pour l'analyse IA (repli LLM)."
                )

            period_context = format_period_context(period_detection, year, month)
            week_anchor_context = ""
            if week_anchor_date is not None:
                week_anchor_context = format_week_anchor_context(
                    week_anchor_date, year, month
                )
            elif scope_input == "weekly" and period_detection.confidence == "low":
                period_detection.warnings.append(
                    "Relevé hebdomadaire sans ancrage de date : vérifiez les numéros "
                    "de jour à l'étape de revue."
                )

            target = roster[0] if (single_employee and roster) else None
            matricule_hint = ""
            known_mats = [
                e.time_tracking_id
                for e in roster
                if (e.time_tracking_id or "").strip()
            ]
            if known_mats:
                matricule_hint = (
                    "\nMatricules GTA connus : "
                    + ", ".join(sorted(set(known_mats))[:30])
                    + ".\n"
                )

            if target is not None:
                full_name = f"{target.first_name} {target.last_name}"
                user_prompt = (
                    "Texte extrait d'un relevé de pointeuse (heures FAITES, nature='reel' "
                    "sauf mention explicite de planning).\n\n"
                    f"{period_context}\n\n"
                    f"Le relevé concerne uniquement le salarié : {full_name}.\n"
                    "Attribue toutes les heures à ce salarié.\n\n"
                    "--- RELEVÉ ---\n"
                    f"{llm_text}"
                )
                system_prompt_name = full_name
            else:
                filtered_roster = _roster_matching_document(llm_text, roster)
                roster_hint = _roster_hint_for_text(filtered_roster, limit=40)
                user_prompt = (
                    "Texte extrait d'un relevé de pointeuse (heures FAITES, nature='reel' "
                    "sauf mention explicite de planning).\n\n"
                    f"{period_context}\n"
                    f"{matricule_hint}\n"
                    "Employés à rapprocher :\n"
                    f"{roster_hint or '(non fourni)'}\n\n"
                    "--- RELEVÉ ---\n"
                    f"{llm_text}"
                )
                system_prompt_name = None

            result = extract_structured_json(
                system_prompt=_build_timesheet_system_prompt(
                    year,
                    month,
                    default_nature,
                    system_prompt_name,
                    period_context=period_context,
                    week_anchor_context=week_anchor_context,
                ),
                user_prompt=user_prompt,
                json_schema=_PROPOSAL_JSON_SCHEMA,
                schema_name="timesheet_extraction",
                model=MODEL_TIMESHEET_EXTRACTION,
                max_tokens=8192,
            )
            if result is None:
                if cegid_result.format_detected and cegid_result.employees:
                    response = _build_proposal_from_cegid(
                        year=year,
                        month=month,
                        source=f"relevé Cegid ({method})",
                        parse_result=cegid_result,
                        roster=roster,
                        default_nature=default_nature,
                    )
                    detected_format = detected_parser or "cegid_weekly"
                    parse_confidence = cegid_result.confidence
                else:
                    raise ScheduleAppError(
                        "error",
                        "L'analyse du relevé a échoué. Vérifiez la lisibilité du document.",
                        status_code=502,
                    )
            elif target is not None:
                response = _build_single_employee_proposal(
                    year=year,
                    month=month,
                    source=f"relevé ({method})",
                    extracted=result.data,
                    target=target,
                    default_nature=default_nature,
                )
                detected_format = "llm"
            else:
                response = _build_proposal(
                    year=year,
                    month=month,
                    source=f"relevé ({method})",
                    extracted=result.data,
                    roster=roster,
                    default_nature=default_nature,
                )
                detected_format = "llm"

    final = _finalize_timesheet_proposal(
        response,
        roster=roster,
        company_id=company_id,
        period_detection=period_detection,
        month_auto_corrected=month_auto_corrected,
        requested_year=requested_year if month_auto_corrected else None,
        requested_month=requested_month if month_auto_corrected else None,
        month_correction_message=correction_msg,
        detected_format=detected_format,
        parse_confidence=parse_confidence,
        extraction_method=method,
        extraction_warnings=extraction_warnings,
        extraction_pages_total=extraction_meta.ocr_pages_total or None,
        extraction_pages_processed=extraction_meta.ocr_pages_processed or None,
        extraction_truncated=extraction_meta.truncated,
    )

    if company_id and not skip_audit:
        record_schedule_import_run(
            company_id=company_id,
            user_id=user_id,
            filename=filename,
            proposal=final,
            file_content=file_content,
            extraction_method=method,
            raw_ocr_text=text,
            import_job_id=import_job_id,
            extraction_mode=timesheet_extract_mode()
            if timesheet_extract_mode() != "hybrid"
            else None,
        )

    return final


__all__ = ["extract_timesheet", "parse_instruction"]
