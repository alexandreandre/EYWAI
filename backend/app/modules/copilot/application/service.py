"""Service applicatif du Copilot à catalogue fermé d'outils."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.modules.copilot.application.dto import AgentMessageDto
from app.modules.copilot.application.tool_service import execute_tool
from app.modules.copilot.domain.filter_values import ValeurDeFiltreInconnue
from app.modules.copilot.domain.tools import parse_tool_calls
from app.modules.copilot.infrastructure.providers import (
    get_collective_agreement_provider,
    get_employee_search_provider,
    get_openai_provider,
    get_user_company_resolver,
)
from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE
from app.modules.copilot.infrastructure.queries import (
    get_company_name as queries_get_company_name,
)


# --- Agent : résolution contexte et données ---


def get_company_id_for_user(user_id: str) -> str | None:
    """Récupère le company_id du profil utilisateur. Délègue à UserCompanyResolver."""
    return get_user_company_resolver().get_company_id_for_user(user_id)


def fuzzy_search_employee(
    name_query: str, company_id: str, threshold: float = 0.6
) -> List[Dict[str, Any]]:
    """Recherche floue d'employés par nom, limitée à l'entreprise active. Délègue à EmployeeSearchProvider."""
    return get_employee_search_provider().fuzzy_search_by_name(
        name_query, company_id, threshold
    )


def get_company_collective_agreements(company_id: str) -> List[Dict[str, Any]]:
    """Récupère les conventions collectives de l'entreprise. Délègue à CollectiveAgreementProvider."""
    return get_collective_agreement_provider().get_company_agreements(company_id)


def _build_agreements_summary(company_agreements: List[Dict[str, Any]]) -> str:
    """Construit le résumé des conventions assignées pour le prompt LLM."""
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


def execute_tool_calls(
    raw_tool_calls: Any,
    company_id: str,
    user_id: str = "",
    user_role: str = "",
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
        return [
            {
                "tool": None,
                "success": False,
                "error": "Appel d'outil invalide.",
            }
        ]

    results: List[Dict[str, Any]] = []
    for call in calls:
        try:
            data = execute_tool(call, company_id, user_id, user_role)
            results.append(
                {"tool": str(call.tool), "success": True, "data": data}
            )
        except ValeurDeFiltreInconnue as exc:
            # Le filtre demandé n'existe pas : on le dit, plutôt que de laisser
            # croire à une panne — ou pire, de répondre « aucun » à tort.
            logging.info("Filtre inconnu pour %s: %s", call.tool, exc)
            results.append(
                {"tool": str(call.tool), "success": False, "error": str(exc)}
            )
        except Exception as exc:  # noqa: BLE001 - on isole chaque outil
            logging.error(
                "Erreur d'exécution de l'outil %s: %s",
                call.tool,
                exc,
                exc_info=True,
            )
            results.append(
                {
                    "tool": str(call.tool),
                    "success": False,
                    "error": "L'outil de données est temporairement indisponible.",
                }
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
    sources: List[tuple[str, str]] | None = None,
    company_name: str = "",
) -> str:
    """Synthétise les résultats en réponse finale. Délègue à OpenAIProvider.

    ``sources`` porte les réponses déjà rédigées par les autres branches
    (convention collective, aide logiciel) quand la question en relève aussi.
    """
    return get_openai_provider().synthesize_final_answer(
        prompt, plan, retrieval_results, sources=sources, company_name=company_name
    )


def get_company_name(company_id: str) -> str:
    """Nom de l'entreprise active. Délègue aux requêtes du module."""
    return queries_get_company_name(company_id)
