"""
Service applicatif du module copilot.

Orchestration uniquement : délègue au domain (règles) et à l'infrastructure (providers, sql_executor, queries).
Aucun accès direct à la DB ni à OpenAI ; comportement strictement identique au legacy.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.modules.copilot.application.dto import AgentMessageDto
from app.modules.copilot.application.tool_service import execute_tool
from app.modules.copilot.domain.rules import only_select_allowed
from app.modules.copilot.domain.tools import parse_tool_calls
from app.modules.copilot.infrastructure.providers import (
    get_collective_agreement_provider,
    get_employee_search_provider,
    get_openai_provider,
    get_user_company_resolver,
)
from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE
from app.modules.copilot.infrastructure.schema_context import (
    DATABASE_SCHEMA_TEXT_TO_SQL,
)
from app.modules.copilot.infrastructure.sql_executor import get_sql_executor


# --- Text-to-SQL ---


def generate_sql_from_prompt(prompt: str, company_id: str | None = None) -> str:
    """Génère une requête SQL à partir du prompt. Délègue à OpenAIProvider.

    ``company_id`` est injecté dans le schéma pour forcer le filtrage sur
    l'entreprise active (sinon le LLM recopie le placeholder et ne trouve rien).
    """
    openai_provider = get_openai_provider()
    return openai_provider.generate_sql_from_prompt(
        prompt, DATABASE_SCHEMA_TEXT_TO_SQL, company_id
    )


def format_answer_from_data(prompt: str, data: Any, sql_query: str) -> str:
    """Formate les données brutes en réponse naturelle. Délègue à OpenAIProvider."""
    return get_openai_provider().format_answer_from_data(prompt, data, sql_query)


def execute_sql_query(query: str) -> Any:
    """Exécute une requête SQL en lecture. Délègue à SupabaseSqlExecutor."""
    return get_sql_executor().execute_read_only(query)


# --- Agent : résolution contexte et données ---


def get_company_id_for_user(user_id: str) -> str | None:
    """Récupère le company_id du profil utilisateur. Délègue à UserCompanyResolver."""
    return get_user_company_resolver().get_company_id_for_user(user_id)


def fuzzy_search_employee(
    name_query: str, threshold: float = 0.6, company_id: str | None = None
) -> List[Dict[str, Any]]:
    """Recherche floue d'employés par nom, limitée à l'entreprise active. Délègue à EmployeeSearchProvider."""
    return get_employee_search_provider().fuzzy_search_by_name(
        name_query, threshold, company_id
    )


def get_company_collective_agreements(company_id: str) -> List[Dict[str, Any]]:
    """Récupère les conventions collectives de l'entreprise. Délègue à CollectiveAgreementProvider."""
    return get_collective_agreement_provider().get_company_agreements(company_id)


def _build_agreements_summary(company_agreements: List[Dict[str, Any]]) -> str:
    """Construit le résumé des conventions pour le prompt LLM (comportement identique au legacy)."""
    if company_agreements:
        agreements_list = [
            f"  - {a['name']} (IDCC: {a['idcc']}) - "
            f"{'✓ Texte disponible' if a['has_text_cached'] else '⚠ Texte non disponible'}"
            for a in company_agreements
        ]
        return "\n\nConventions collectives assignées à l'entreprise:\n" + "\n".join(
            agreements_list
        )
    return "\n\nAucune convention collective assignée à l'entreprise."


def analyze_intent_and_plan(
    prompt: str,
    conversation_history: List[AgentMessageDto],
    company_agreements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyse l'intention et retourne un plan. Délègue à OpenAIProvider."""
    openai_provider = get_openai_provider()
    conversation_as_dicts = [
        {"role": msg.role, "content": msg.content} for msg in conversation_history
    ]
    agreements_summary = _build_agreements_summary(company_agreements)
    return openai_provider.analyze_intent_and_plan(
        prompt, conversation_as_dicts, agreements_summary
    )


def execute_retrieval_step(
    step_description: str, context: Dict[str, Any]
) -> Dict[str, Any]:
    """Exécute une étape de récupération : génération SQL (OpenAI) + règle SELECT (domain) + exécution (infra)."""
    openai_provider = get_openai_provider()
    sql_executor = get_sql_executor()
    try:
        sql_query = openai_provider.generate_sql_for_step(step_description, context)
        if not only_select_allowed(sql_query):
            logging.warning("Requête non-SELECT bloquée: %s", sql_query)
            return {"error": "Requête non autorisée", "success": False}
        logging.info("Exécution SQL: %s", sql_query)
        raw_data = sql_executor.execute_read_only(sql_query)
        return {"sql": sql_query, "data": raw_data, "success": True}
    except Exception as e:
        logging.error("Erreur lors de l'exécution de l'étape: %s", e)
        return {"error": str(e), "success": False}


def execute_tool_calls(
    raw_tool_calls: Any, company_id: str
) -> List[Dict[str, Any]]:
    """Parse et exécute une liste d'appels d'outils avec le company_id serveur.

    Chemin sécurisé (catalogue fermé) destiné à remplacer l'orchestration SQL :
    - le parsing (domain) rejette tout outil inconnu, tout ``company_id`` ou SQL
      fourni par le LLM, et limite le nombre d'appels ;
    - en cas d'échec de parsing, on renvoie un marqueur d'erreur (fail-closed)
      sans exécuter aucune requête ;
    - chaque outil est exécuté avec le ``company_id`` serveur imposé, jamais une
      valeur issue du LLM.
    """
    try:
        calls = parse_tool_calls(raw_tool_calls)
    except ValueError as exc:
        logging.warning("Appels d'outils Copilot invalides: %s", exc)
        return [{"tool": None, "success": False, "error": str(exc)}]

    results: List[Dict[str, Any]] = []
    for call in calls:
        try:
            data = execute_tool(call, company_id)
            results.append(
                {"tool": str(call.tool), "success": True, "data": data}
            )
        except Exception as exc:  # noqa: BLE001 - on isole chaque outil
            logging.error("Erreur d'exécution de l'outil %s: %s", call.tool, exc)
            results.append(
                {"tool": str(call.tool), "success": False, "error": str(exc)}
            )
    return results


def answer_collective_agreement_question(
    prompt: str, agreement: Dict[str, Any], plan: Dict[str, Any]
) -> str:
    """Répond à une question sur une convention collective. Délègue à OpenAIProvider."""
    return get_openai_provider().answer_collective_agreement_question(
        prompt, agreement, plan
    )


def answer_app_usage_question(
    prompt: str, conversation_history: List[AgentMessageDto]
) -> str:
    """Répond à une question d'aide à l'utilisation du logiciel. Délègue à OpenAIProvider."""
    conversation_as_dicts = [
        {"role": msg.role, "content": msg.content} for msg in conversation_history
    ]
    return get_openai_provider().answer_app_usage_question(
        prompt, conversation_as_dicts, APP_FEATURE_GUIDE
    )


def synthesize_final_answer(
    prompt: str,
    plan: Dict[str, Any],
    retrieval_results: List[Dict[str, Any]],
) -> str:
    """Synthétise les résultats en réponse finale. Délègue à OpenAIProvider."""
    return get_openai_provider().synthesize_final_answer(
        prompt, plan, retrieval_results
    )
