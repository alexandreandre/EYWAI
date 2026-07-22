"""
Commandes du Copilot à catalogue fermé d'outils RH.

Le flux agent délègue la planification et la synthèse au LLM, mais seules les
requêtes typées et scopées du catalogue peuvent accéder aux données.
"""

from __future__ import annotations

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
logger = get_logger(__name__)


def execute_text_to_sql(input_: TextToSqlInput) -> TextToSqlResult:
    """Désactive définitivement l'ancien endpoint Text-to-SQL.

    Le feature flag historique ne peut pas réactiver ce chemin : toutes les
    données RH du Copilot passent désormais par le catalogue fermé d'outils.
    """
    raise DataRetrievalDisabledError(COPILOT_DATA_UNAVAILABLE_MESSAGE)


def handle_agent_query(input_: AgentQueryInput) -> AgentQueryResult:
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
        return AgentQueryResult(
            answer="",
            needs_clarification=True,
            clarification_question=plan.get("clarification_question"),
        )

    if plan.get("requires_app_help"):
        answer = answer_app_usage_question(prompt, conversation_history)
        return AgentQueryResult(
            answer=answer,
            needs_clarification=False,
        )

    if (
        not company_id
        and plan.get("requires_data_retrieval")
        and not is_rh_data_enabled()
    ):
        return AgentQueryResult(
            answer=COPILOT_DATA_UNAVAILABLE_MESSAGE,
            needs_clarification=False,
        )

    if not company_id:
        raise LookupError("Company ID non trouvé pour cet utilisateur")

    if plan.get("requires_collective_agreement"):
        if not company_agreements:
            return AgentQueryResult(
                answer=(
                    "Votre entreprise n'a aucune convention collective assignée pour le moment. "
                    "Veuillez contacter votre administrateur pour en ajouter une."
                ),
                needs_clarification=False,
            )

        if len(company_agreements) == 1:
            selected_agreement = company_agreements[0]
            log_app_debug(
                logger,
                "Une seule convention trouvée, utilisation automatique: %s",
                selected_agreement['name'],
            )
        else:
            collective_agreement_query = plan.get("collective_agreement_query")
            if not collective_agreement_query:
                agreements_list = "\n".join(
                    f"- {a['name']} (IDCC: {a['idcc']})" for a in company_agreements
                )
                return AgentQueryResult(
                    answer="",
                    needs_clarification=True,
                    clarification_question=(
                        f"Votre entreprise a plusieurs conventions collectives. De laquelle parlez-vous ?\n\n{agreements_list}"
                    ),
                )

            selected_agreement = None
            query_lower = collective_agreement_query.lower()
            for agreement in company_agreements:
                name_lower = agreement["name"].lower()
                idcc_lower = agreement["idcc"].lower()
                if (
                    query_lower in name_lower
                    or query_lower in idcc_lower
                    or name_lower in query_lower
                ):
                    selected_agreement = agreement
                    break

            if not selected_agreement:
                agreements_list = "\n".join(
                    f"- {a['name']} (IDCC: {a['idcc']})" for a in company_agreements
                )
                return AgentQueryResult(
                    answer="",
                    needs_clarification=True,
                    clarification_question=(
                        f"Je n'ai pas trouvé de convention collective correspondant à '{collective_agreement_query}'. "
                        f"Voici les conventions disponibles :\n\n{agreements_list}\n\nDe laquelle parlez-vous ?"
                    ),
                )

        answer = answer_collective_agreement_question(prompt, selected_agreement, plan)
        return AgentQueryResult(
            answer=answer,
            needs_clarification=False,
        )

    if plan.get("requires_data_retrieval") and not is_rh_data_enabled():
        return AgentQueryResult(
            answer=COPILOT_DATA_UNAVAILABLE_MESSAGE,
            needs_clarification=False,
        )

    retrieval_results = []
    if plan.get("requires_data_retrieval"):
        retrieval_results = execute_tool_calls(
            plan.get("data_tool_calls") or [],
            company_id=company_id,
        )

    final_answer = synthesize_final_answer(prompt, plan, retrieval_results)

    return AgentQueryResult(
        answer=final_answer,
        needs_clarification=False,
    )
