"""
Commandes (cas d'usage) du module copilot.

Orchestration migrée depuis api/routers/copilot.py et api/routers/copilot_agent.py.
Délègue au service pour génération SQL, formatage, intent, conventions, synthèse.
"""
from __future__ import annotations

import json
import logging
import os

from app.modules.copilot.application.dto import (
    AgentQueryInput,
    AgentQueryResult,
    TextToSqlInput,
    TextToSqlResult,
)
from app.modules.copilot.application.service import (
    analyze_intent_and_plan,
    answer_collective_agreement_question,
    execute_retrieval_step,
    execute_sql_query,
    format_answer_from_data,
    fuzzy_search_employee,
    generate_sql_from_prompt,
    get_company_collective_agreements,
    get_company_id_for_user,
    synthesize_final_answer,
)
from app.modules.copilot.domain.rules import only_select_allowed


def execute_text_to_sql(input_: TextToSqlInput) -> TextToSqlResult:
    """
    Exécute une requête Text-to-SQL : génération SQL via LLM, vérification SELECT, exécution, formatage.
    Comportement identique à api/routers/copilot.py handle_query.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Le service Copilote n'est pas configuré (clé API manquante).")

    sql_query = generate_sql_from_prompt(input_.prompt)

    if not only_select_allowed(sql_query):
        logging.warning(f"Requête non-SELECT bloquée: {sql_query}")
        raise PermissionError("Requête non autorisée. Seuls les SELECT sont permis.")

    logging.info(f"Exécution SQL (Text-to-SQL): {sql_query}")
    raw_data = execute_sql_query(sql_query)
    final_answer = format_answer_from_data(input_.prompt, raw_data, sql_query)

    return TextToSqlResult(
        answer=final_answer,
        sql_query=sql_query,
        data=raw_data,
    )


def handle_agent_query(input_: AgentQueryInput) -> AgentQueryResult:
    """
    Traite une requête agent : intent, clarification, recherche employé, conventions collectives,
    récupération données, synthèse. Comportement identique à api/routers/copilot_agent.py handle_agent_query.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Le service Copilote n'est pas configuré.")

    prompt = input_.prompt
    conversation_history = input_.conversation_history or []

    company_id = get_company_id_for_user(input_.user_id)
    if not company_id:
        raise LookupError("Company ID non trouvé pour cet utilisateur")

    company_agreements = get_company_collective_agreements(company_id)
    logging.info(f"Conventions collectives trouvées pour l'entreprise: {len(company_agreements)}")

    plan = analyze_intent_and_plan(prompt, conversation_history, company_agreements)
    thought_process = f"Plan d'action: {json.dumps(plan, ensure_ascii=False, indent=2)}"
    logging.info(thought_process)

    if plan.get("needs_clarification"):
        return AgentQueryResult(
            answer="",
            needs_clarification=True,
            clarification_question=plan.get("clarification_question"),
            thought_process=thought_process,
        )

    if plan.get("requires_collective_agreement"):
        if not company_agreements:
            return AgentQueryResult(
                answer=(
                    "Votre entreprise n'a aucune convention collective assignée pour le moment. "
                    "Veuillez contacter votre administrateur pour en ajouter une."
                ),
                needs_clarification=False,
                thought_process=thought_process,
            )

        if len(company_agreements) == 1:
            selected_agreement = company_agreements[0]
            logging.info(f"Une seule convention trouvée, utilisation automatique: {selected_agreement['name']}")
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
                    thought_process=thought_process,
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
                    thought_process=thought_process,
                )

        answer = answer_collective_agreement_question(prompt, selected_agreement, plan)
        return AgentQueryResult(
            answer=answer,
            needs_clarification=False,
            thought_process=thought_process + f"\n\nConvention utilisée: {selected_agreement['name']}",
        )

    context = {}
    if plan.get("requires_employee_search") and plan.get("employee_query"):
        employee_matches = fuzzy_search_employee(plan.get("employee_query"))

        if not employee_matches:
            return AgentQueryResult(
                answer=(
                    f"Je n'ai trouvé aucun employé correspondant à '{plan.get('employee_query')}'. "
                    "Pouvez-vous vérifier l'orthographe ou me donner plus de détails ?"
                ),
                needs_clarification=False,
                thought_process=thought_process,
            )

        if len(employee_matches) > 1 and employee_matches[0]["similarity"] < 0.95:
            names = [m["full_name"] for m in employee_matches[:3]]
            return AgentQueryResult(
                answer="",
                needs_clarification=True,
                clarification_question=(
                    f"J'ai trouvé plusieurs employés possibles : {', '.join(names)}. De qui parlez-vous exactement ?"
                ),
                thought_process=thought_process,
            )

        best_match = employee_matches[0]["employee"]
        context["employee_id"] = best_match["id"]
        context["employee_name"] = f"{best_match['first_name']} {best_match['last_name']}"
        logging.info(
            f"Employé identifié: {context['employee_name']} (similarité: {employee_matches[0]['similarity']})"
        )

    retrieval_results = []
    if plan.get("requires_data_retrieval"):
        steps = plan.get("data_retrieval_steps", ["Récupérer les données demandées"])
        for step in steps:
            logging.info(f"Exécution de l'étape: {step}")
            result = execute_retrieval_step(step, context)
            retrieval_results.append(result)

    final_answer = synthesize_final_answer(prompt, plan, retrieval_results)
    sql_queries = [
        r.get("sql")
        for r in retrieval_results
        if r.get("success") and r.get("sql")
    ]
    all_data = [
        r.get("data")
        for r in retrieval_results
        if r.get("success") and r.get("data")
    ]

    return AgentQueryResult(
        answer=final_answer,
        needs_clarification=False,
        sql_queries=sql_queries if sql_queries else None,
        data=all_data if all_data else None,
        thought_process=thought_process,
    )
