"""
Commandes du Copilot à catalogue fermé d'outils RH.

Le flux agent délègue la planification et la synthèse au LLM, mais seules les
requêtes typées et scopées du catalogue peuvent accéder aux données.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

from app.core.logging import get_logger, log_app_debug
from app.shared.infrastructure.ai import is_llm_configured
from app.modules.copilot.application.dto import (
    AgentQueryInput,
    AgentQueryResult,
    TextToSqlInput,
    TextToSqlResult,
)
from app.modules.copilot.application.service import (
    analyze_intent_and_plan,
    answer_app_usage_question,
    answer_collective_agreement_question,
    execute_tool_calls,
    get_company_collective_agreements,
    synthesize_final_answer,
)
from app.modules.copilot.domain.data_access import (
    COPILOT_DATA_UNAVAILABLE_MESSAGE,
    DataRetrievalDisabledError,
    is_rh_data_enabled,
)
from app.modules.copilot.infrastructure.journal import enregistrer_tour
logger = get_logger(__name__)


def execute_text_to_sql(input_: TextToSqlInput) -> TextToSqlResult:
    """Désactive définitivement l'ancien endpoint Text-to-SQL.

    Le feature flag historique ne peut pas réactiver ce chemin : toutes les
    données RH du Copilot passent désormais par le catalogue fermé d'outils.
    """
    raise DataRetrievalDisabledError(COPILOT_DATA_UNAVAILABLE_MESSAGE)


def handle_agent_query(input_: AgentQueryInput) -> AgentQueryResult:
    """Traite une requête agent, et journalise le tour.

    Le journal encadre le traitement sans jamais le modifier : une écriture
    impossible n'empêche pas la réponse, et une exception métier est journalisée
    puis relancée telle quelle.
    """
    debut = time.monotonic()
    trace: Dict[str, Any] = {"routage": "aucune", "outils": []}
    try:
        resultat = _traiter_agent_query(input_, trace)
    except Exception as exc:
        _journaliser(input_, trace, debut, reponse="", erreur=f"{type(exc).__name__}: {exc}")
        raise
    _journaliser(input_, trace, debut, reponse=resultat.answer or resultat.clarification_question or "")
    return resultat


def _journaliser(
    input_: AgentQueryInput,
    trace: Dict[str, Any],
    debut: float,
    *,
    reponse: str,
    erreur: str | None = None,
) -> None:
    enregistrer_tour(
        company_id=input_.active_company_id,
        user_id=input_.user_id,
        question=input_.prompt,
        routage=str(trace.get("routage") or "aucune"),
        outils=list(trace.get("outils") or []),
        latence_ms=int((time.monotonic() - debut) * 1000),
        reponse_caracteres=len(reponse or ""),
        erreur=erreur,
    )


def _traiter_agent_query(
    input_: AgentQueryInput, trace: Dict[str, Any]
) -> AgentQueryResult:
    """
    Traite une requête agent : intent, clarification, recherche employé, conventions collectives,
    récupération données, synthèse. Comportement identique à api/routers/copilot_agent.py handle_agent_query.
    """
    if not is_llm_configured():
        raise ValueError(
            "Le service Copilote n'est pas configuré (OPENROUTER_API_KEY manquante)."
        )

    prompt = input_.prompt
    conversation_history = input_.conversation_history or []

    # L'entreprise active, validée par la dépendance HTTP, est l'unique contexte permis.
    company_id = input_.active_company_id

    company_agreements = (
        get_company_collective_agreements(company_id) if company_id else []
    )
    log_app_debug(
        logger,
        "Conventions collectives trouvées pour l'entreprise: %s",
        len(company_agreements),
    )

    plan = analyze_intent_and_plan(prompt, conversation_history, company_agreements)
    if plan.get("needs_clarification"):
        trace["routage"] = "clarif"
        return AgentQueryResult(
            answer="",
            needs_clarification=True,
            clarification_question=plan.get("clarification_question"),
        )

    besoin_aide = bool(plan.get("requires_app_help"))
    besoin_convention = bool(plan.get("requires_collective_agreement"))
    besoin_donnees = bool(plan.get("requires_data_retrieval"))
    trace["routage"] = (
        "cc" if besoin_convention
        else "data" if besoin_donnees
        else "app_help" if besoin_aide
        else "aucune"
    )

    # L'aide à l'utilisation du logiciel ne dépend pas de l'entreprise : quand
    # c'est la seule chose demandée, elle répond sans contexte société.
    if besoin_aide and not besoin_convention and not besoin_donnees:
        return AgentQueryResult(
            answer=answer_app_usage_question(prompt, conversation_history),
            needs_clarification=False,
        )

    if not company_id and besoin_donnees and not is_rh_data_enabled():
        return AgentQueryResult(
            answer=COPILOT_DATA_UNAVAILABLE_MESSAGE,
            needs_clarification=False,
        )

    if not company_id:
        raise LookupError("Company ID non trouvé pour cet utilisateur")

    # Une question peut relever de plusieurs familles à la fois (« combien j'ai
    # de CDI, et que dit la convention sur leur période d'essai ? »). On collecte
    # donc chaque source avant de répondre, au lieu de sortir à la première.
    sources: list[tuple[str, str]] = []
    retrieval_results: list[dict] = []

    if besoin_convention:
        selection = _resoudre_convention(plan, company_agreements)
        if selection.clarification:
            trace["routage"] = "clarif"
            return AgentQueryResult(
                answer="",
                needs_clarification=True,
                clarification_question=selection.clarification,
            )
        if selection.agreement is None:
            sources.append(("Convention collective", selection.message))
        else:
            sources.append(
                (
                    "Convention collective",
                    answer_collective_agreement_question(
                        prompt, selection.agreement, plan
                    ),
                )
            )

    if besoin_donnees:
        if not is_rh_data_enabled():
            sources.append(("Données RH", COPILOT_DATA_UNAVAILABLE_MESSAGE))
        else:
            retrieval_results = execute_tool_calls(
                plan.get("data_tool_calls") or [],
                company_id=company_id,
            )
            trace["outils"] = [
                str(r.get("tool")) for r in retrieval_results if r.get("tool")
            ]

    if besoin_aide:
        sources.append(
            ("Utilisation du logiciel", answer_app_usage_question(prompt, conversation_history))
        )

    # Une seule source et aucune donnée : on rend sa réponse telle quelle, sans
    # passer par une synthèse qui n'ajouterait rien.
    if len(sources) == 1 and not retrieval_results:
        return AgentQueryResult(answer=sources[0][1], needs_clarification=False)

    final_answer = synthesize_final_answer(
        prompt, plan, retrieval_results, sources=sources
    )

    return AgentQueryResult(
        answer=final_answer,
        needs_clarification=False,
    )


@dataclass
class _SelectionConvention:
    """Résultat de la résolution de la convention à interroger."""

    agreement: dict | None = None
    clarification: str | None = None
    message: str = ""


def _resoudre_convention(
    plan: dict, company_agreements: list[dict]
) -> _SelectionConvention:
    """Choisit la convention à interroger, ou la question à poser en retour."""
    if not company_agreements:
        return _SelectionConvention(
            message=(
                "Votre entreprise n'a aucune convention collective assignée pour le moment. "
                "Veuillez contacter votre administrateur pour en ajouter une."
            )
        )

    if len(company_agreements) == 1:
        log_app_debug(
            logger,
            "Une seule convention trouvée, utilisation automatique: %s",
            company_agreements[0]["name"],
        )
        return _SelectionConvention(agreement=company_agreements[0])

    liste = "\n".join(
        f"- {a['name']} (IDCC: {a['idcc']})" for a in company_agreements
    )
    demandee = plan.get("collective_agreement_query")
    if not demandee:
        return _SelectionConvention(
            clarification=(
                "Votre entreprise a plusieurs conventions collectives. "
                f"De laquelle parlez-vous ?\n\n{liste}"
            )
        )

    demandee_min = demandee.lower()
    for agreement in company_agreements:
        nom = agreement["name"].lower()
        if (
            demandee_min in nom
            or demandee_min in agreement["idcc"].lower()
            or nom in demandee_min
        ):
            return _SelectionConvention(agreement=agreement)

    return _SelectionConvention(
        clarification=(
            f"Je n'ai pas trouvé de convention collective correspondant à '{demandee}'. "
            f"Voici les conventions disponibles :\n\n{liste}\n\nDe laquelle parlez-vous ?"
        )
    )
