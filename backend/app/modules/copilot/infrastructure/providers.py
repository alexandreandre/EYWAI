"""
Providers infrastructure : OpenAI, recherche employés, conventions collectives, résolution company.

Implémentent les interfaces du domain. Comportement strictement identique au legacy.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List

from openai import OpenAI

from app.modules.copilot.infrastructure.schema_context import DATABASE_SCHEMA_AGENT
from app.modules.copilot.infrastructure.queries import (
    get_company_collective_agreements as queries_get_company_agreements,
    get_company_id_for_user as queries_get_company_id,
    get_employees_for_fuzzy_search,
)


def _clean_generated_sql(raw_sql: str) -> str:
    """Retire les marqueurs ``` et le point-virgule final du SQL généré par le LLM."""
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("\n", 1)[0]
    return sql.strip().rstrip(";")


def _get_openai_client() -> OpenAI:
    """Retourne un client OpenAI configuré (clé depuis l'environnement)."""
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=api_key or "")


# --- OpenAI Provider (IOpenAIProvider) ---


class OpenAIProvider:
    """Implémentation des appels LLM pour Text-to-SQL et Agent."""

    def generate_sql_from_prompt(self, prompt: str, schema_context: str) -> str:
        today = date.today().isoformat()
        schema = (
            schema_context.format(today=today)
            if "{today}" in schema_context
            else schema_context
        )
        client = _get_openai_client()
        system_prompt = f"""
        Tu es un expert en génération de SQL PostgreSQL.
        En te basant sur le schéma de BDD suivant, génère une requête SQL (SELECT uniquement)
        pour répondre à la question de l'utilisateur.
        Ne réponds que par le code SQL, sans aucune explication.
        Aujourd'hui, nous sommes le {today}.

        Schéma:
        {schema}
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        sql_query = (response.choices[0].message.content or "").strip()
        return _clean_generated_sql(sql_query)

    def format_answer_from_data(self, prompt: str, data: Any, sql_query: str) -> str:
        client = _get_openai_client()
        if data is None or data == []:
            data_str = "[] (Aucun résultat)"
        else:
            data_str = json.dumps(data, indent=2, default=str)
        system_prompt = f"""
        Tu es un assistant RH. Réponds à la question de l'utilisateur en te basant
        sur les données brutes suivantes (résultat de la requête SQL).
        Sois concis et direct. Si les données sont vides ou '[]',
        indique simplement qu'aucun résultat n'a été trouvé.
        Question: {prompt}
        Requête SQL: {sql_query}
        Données:
        {data_str}
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}],
                temperature=0,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error("Erreur lors du formatage de la réponse: %s", e)
            return "J'ai trouvé des données, mais je n'ai pas pu les formater. (Erreur LLM)"

    def analyze_intent_and_plan(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        company_agreements_summary: str,
    ) -> Dict[str, Any]:
        client = _get_openai_client()
        conversation_context = "\n".join(
            f"{msg.get('role', '')}: {msg.get('content', '')}" for msg in conversation_history[-5:]
        )
        system_prompt = f"""Tu es un agent RH intelligent qui aide à répondre aux questions sur les employés ET les conventions collectives.

Date actuelle: {date.today().isoformat()}

Schéma de la base de données:
{DATABASE_SCHEMA_AGENT}
{company_agreements_summary}

Historique de conversation récent:
{conversation_context}

Ton rôle est d'analyser la demande de l'utilisateur et de créer un plan d'action.

Tu dois retourner un JSON avec cette structure:
{{
  "intent": "description de l'intention en une phrase",
  "needs_clarification": true/false,
  "clarification_question": "question à poser si besoin de clarification" ou null,
  "requires_employee_search": true/false,
  "employee_query": "nom de l'employé à rechercher" ou null,
  "requires_collective_agreement": true/false,
  "collective_agreement_query": "convention collective concernée ou null si ambiguë" ou null,
  "agreement_id_if_unique": "id de la convention si une seule existe" ou null,
  "requires_data_retrieval": true/false,
  "data_retrieval_steps": ["étape 1", "étape 2", ...]
}}

Règles importantes:
1. Si le nom d'un employé est mentionné mais semble incomplet ou ambigu, demande une clarification
2. Si la question nécessite plusieurs données (ex: "combien gagne X et Y"), prévois plusieurs étapes
3. Si la question est vague (ex: "combien d'employés"), demande de préciser (type de contrat? statut?)
4. **NOUVEAU**: Si la question concerne une convention collective, active requires_collective_agreement: true
5. **NOUVEAU**: Si plusieurs conventions existent et que la question ne précise pas laquelle, demande une clarification
6. **NOUVEAU**: Si une seule convention existe, utilise-la automatiquement (agreement_id_if_unique)
7. Détecte les questions sur conventions: congés, RTT, temps de travail, période d'essai, préavis, jours fériés, classifications, etc.

Exemples:
- "Combien gagne Jean" → requires_employee_search: true, requires_data_retrieval: true
- "Nombre d'employés" → needs_clarification: true (tous? CDI seulement? cadres?)
- "Combien de jours de congés payés par an ?" → requires_collective_agreement: true
- "Quelle est la durée de la période d'essai ?" → requires_collective_agreement: true
- "Congés payés selon la convention" → requires_collective_agreement: true (si plusieurs conventions, demande laquelle)
- "Que dit la convention SYNTEC sur les RTT ?" → requires_collective_agreement: true, collective_agreement_query: "SYNTEC"

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Question: {prompt}"},
                ],
                temperature=0.3,
            )
            plan_json = (response.choices[0].message.content or "").strip()
            if plan_json.startswith("```"):
                plan_json = plan_json.split("\n", 1)[1].rsplit("\n", 1)[0]
                if plan_json.startswith("json"):
                    plan_json = plan_json[4:].strip()
            return json.loads(plan_json)
        except Exception as e:
            logging.error("Erreur lors de l'analyse d'intention: %s", e)
            return {
                "intent": "Unknown",
                "needs_clarification": False,
                "requires_employee_search": False,
                "requires_data_retrieval": True,
                "data_retrieval_steps": ["Requête SQL simple"],
                "estimated_sql_queries": [],
            }

    def generate_sql_for_step(self, step_description: str, context: Dict[str, Any]) -> str:
        client = _get_openai_client()
        system_prompt = f"""Tu es un expert en génération de SQL PostgreSQL.
Génère une requête SQL SELECT pour: {step_description}

Contexte: {json.dumps(context, default=str)}

Schéma de la base de données:
{DATABASE_SCHEMA_AGENT}

Date actuelle: {date.today().isoformat()}

Réponds UNIQUEMENT avec la requête SQL, sans ```sql ni explication."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0,
        )
        sql_query = (response.choices[0].message.content or "").strip().rstrip(";")
        if sql_query.startswith("```"):
            sql_query = sql_query.split("\n", 1)[1].rsplit("\n", 1)[0]
        return sql_query.strip()

    def answer_collective_agreement_question(
        self, prompt: str, agreement: Dict[str, Any], plan: Dict[str, Any]
    ) -> str:
        client = _get_openai_client()
        if not agreement.get("full_text"):
            return (
                f"Je ne peux pas répondre à cette question car le texte de la convention collective "
                f"'{agreement['name']}' n'est pas encore disponible en cache. "
                "Veuillez d'abord consulter le PDF de la convention pour initialiser le cache."
            )
        agreement_name = agreement["name"]
        agreement_idcc = agreement["idcc"]
        agreement_description = agreement.get("description", "")
        full_text = agreement["full_text"]
        if len(full_text) > 150000:
            full_text = full_text[:150000] + "\n\n[...Document tronqué...]"

        system_prompt = f"""Tu es un assistant expert spécialisé dans la convention collective suivante :

📋 **Convention Collective : {agreement_name}**
🔢 **IDCC : {agreement_idcc}**
{f'📝 **Description : {agreement_description}**' if agreement_description else ''}

Tu as une connaissance complète et détaillée de cette convention collective. Ton rôle est de :

**🎯 Objectifs :**
1. Répondre aux questions sur cette convention collective de manière précise et professionnelle
2. Citer les articles ou sections pertinents de la convention
3. Expliquer clairement les droits et obligations des employeurs et employés
4. Donner des réponses pratiques et applicables

**📏 Règles strictes :**
- Base-toi UNIQUEMENT sur le texte de la convention collective fourni
- Si l'information n'est pas dans la convention, indique-le clairement
- Cite toujours les articles/sections pertinents quand c'est possible
- Sois précis et factuel
- Si une question nécessite une interprétation juridique complexe ou sort du cadre de la convention, recommande de consulter un avocat spécialisé en droit du travail
- Utilise un ton professionnel mais accessible
- Structure tes réponses de manière claire (utilise des puces, des numéros, etc.)

**⚠️ Important :**
- Ne donne jamais de conseils juridiques définitifs
- En cas de doute, recommande de consulter un expert
- Mentionne si une disposition peut avoir évolué ou nécessite une vérification avec la version la plus récente

Contexte de la demande: {json.dumps(plan, ensure_ascii=False)}"""

        user_prompt = f"""Voici le texte complet de la convention collective {agreement_name} (IDCC {agreement_idcc}) :

---
{full_text}
---

**Question de l'utilisateur :**
{prompt}

**Instructions :**
Réponds à cette question en te basant sur le texte de la convention collective ci-dessus. Cite les articles ou sections pertinents et structure ta réponse de manière claire et professionnelle."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error("Erreur lors de la réponse sur la convention collective: %s", e)
            return f"Je rencontre des difficultés pour répondre à votre question sur la convention collective. Erreur: {str(e)}"

    def synthesize_final_answer(
        self,
        prompt: str,
        plan: Dict[str, Any],
        retrieval_results: List[Dict[str, Any]],
    ) -> str:
        client = _get_openai_client()
        results_summary = []
        for i, result in enumerate(retrieval_results):
            if result.get("success"):
                results_summary.append(
                    f"Étape {i+1} - SQL: {result.get('sql')}\nDonnées: "
                    f"{json.dumps(result.get('data'), default=str, ensure_ascii=False)}"
                )
            else:
                results_summary.append(f"Étape {i+1} - Erreur: {result.get('error')}")
        results_text = "\n\n".join(results_summary)

        system_prompt = f"""Tu es un assistant RH professionnel et convivial, expert en données RH et en conventions collectives.

Question de l'utilisateur: {prompt}

Plan d'action: {json.dumps(plan, ensure_ascii=False)}

Résultats des requêtes:
{results_text}

Date actuelle: {date.today().isoformat()}

Génère une réponse claire, professionnelle et concise en français.
- Utilise des phrases complètes et naturelles
- Mets en avant les informations importantes
- Si plusieurs employés sont mentionnés, structure ta réponse clairement
- Si des données manquent, explique-le poliment
- Ajoute du contexte si utile (ex: "Ce qui représente X% du salaire total")
- Si la question concerne des éléments qui pourraient être régis par une convention collective (congés, RTT, période d'essai, etc.), mentionne-le et suggère de consulter la convention collective de l'entreprise pour plus de détails

Ne mentionne JAMAIS les détails techniques (SQL, tables, etc.). Réponds comme un collègue RH serviable et expert."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}],
                temperature=0.7,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error("Erreur lors de la synthèse: %s", e)
            return "Je rencontre des difficultés pour synthétiser ces informations. Pouvez-vous reformuler votre question ?"


# --- Employee search (IEmployeeSearch) ---


class EmployeeSearchProvider:
    """Recherche floue d'employés par nom (comportement identique au legacy)."""

    def fuzzy_search_by_name(
        self, name_query: str, threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        try:
            all_employees = get_employees_for_fuzzy_search()
            if not all_employees:
                return []

            query_lower = name_query.lower().strip()
            matches = []
            for emp in all_employees:
                first_name = (emp.get("first_name") or "").lower()
                last_name = (emp.get("last_name") or "").lower()
                full_name = f"{first_name} {last_name}"
                similarities = [
                    SequenceMatcher(None, query_lower, full_name).ratio(),
                    SequenceMatcher(None, query_lower, first_name).ratio(),
                    SequenceMatcher(None, query_lower, last_name).ratio(),
                    SequenceMatcher(None, query_lower, f"{last_name} {first_name}").ratio(),
                ]
                max_similarity = max(similarities)
                if max_similarity >= threshold:
                    matches.append({
                        "employee": emp,
                        "similarity": max_similarity,
                        "full_name": f"{emp.get('first_name')} {emp.get('last_name')}",
                    })
            matches.sort(key=lambda x: x["similarity"], reverse=True)
            return matches
        except Exception as e:
            logging.error("Erreur lors de la recherche floue: %s", e)
            return []


# --- Collective agreement provider (ICollectiveAgreementProvider) ---


class CollectiveAgreementProvider:
    """Fournit les conventions collectives assignées à une entreprise avec texte en cache."""

    def get_company_agreements(self, company_id: str) -> List[Dict[str, Any]]:
        return queries_get_company_agreements(company_id)


# --- User company resolver (IUserCompanyResolver) ---


class UserCompanyResolver:
    """Résout le company_id à partir de l'utilisateur connecté."""

    def get_company_id_for_user(self, user_id: str) -> str | None:
        return queries_get_company_id(user_id)


# Instances partagées (utilisées par le service applicatif)
_openai_provider: OpenAIProvider | None = None
_employee_search_provider: EmployeeSearchProvider | None = None
_collective_agreement_provider: CollectiveAgreementProvider | None = None
_user_company_resolver: UserCompanyResolver | None = None


def get_openai_provider() -> OpenAIProvider:
    global _openai_provider
    if _openai_provider is None:
        _openai_provider = OpenAIProvider()
    return _openai_provider


def get_employee_search_provider() -> EmployeeSearchProvider:
    global _employee_search_provider
    if _employee_search_provider is None:
        _employee_search_provider = EmployeeSearchProvider()
    return _employee_search_provider


def get_collective_agreement_provider() -> CollectiveAgreementProvider:
    global _collective_agreement_provider
    if _collective_agreement_provider is None:
        _collective_agreement_provider = CollectiveAgreementProvider()
    return _collective_agreement_provider


def get_user_company_resolver() -> UserCompanyResolver:
    global _user_company_resolver
    if _user_company_resolver is None:
        _user_company_resolver = UserCompanyResolver()
    return _user_company_resolver
