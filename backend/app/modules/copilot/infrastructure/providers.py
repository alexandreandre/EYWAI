"""
Providers infrastructure : LLM (OpenRouter), recherche employés, conventions collectives, résolution company.

Implémentent les interfaces du domain. Comportement strictement identique au legacy.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List

from app.shared.infrastructure.ai import MODEL_COPILOT, chat_completions_create
from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE
from app.modules.copilot.infrastructure.schema_context import DATABASE_SCHEMA_AGENT
from app.modules.copilot.infrastructure.queries import (
    get_company_collective_agreements as queries_get_company_agreements,
    get_company_id_for_user as queries_get_company_id,
    get_employees_for_fuzzy_search,
)


def _clean_generated_sql(raw_sql: str, company_id: str | None = None) -> str:
    """Retire les marqueurs ``` et le point-virgule final du SQL généré par le LLM.

    Garde-fou : si le LLM a recopié le placeholder ``<company_id>``, on le
    remplace par l'UUID réel de l'entreprise active (évite un WHERE qui ne
    matche aucune ligne).
    """
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[1].rsplit("\n", 1)[0]
    sql = sql.strip().rstrip(";")
    if company_id and "<company_id>" in sql:
        sql = sql.replace("<company_id>", str(company_id))
    return sql


def _inject_runtime_context(schema: str, company_id: str | None) -> str:
    """Remplace les placeholders {today} et <company_id> par les valeurs réelles.

    Sans cette substitution, le LLM recopie littéralement le placeholder
    ``'<company_id>'`` dans le WHERE, ce qui ne matche aucune ligne et donne
    l'impression que l'assistant « ne trouve pas » les salariés.
    """
    result = schema.replace("{today}", date.today().isoformat()) if "{today}" in schema else schema
    if company_id:
        result = result.replace("<company_id>", str(company_id))
    return result


def _company_scope_hint(company_id: str | None) -> str:
    """Instruction explicite pour forcer le filtrage sur l'entreprise active."""
    if not company_id:
        return ""
    return (
        f"\n\nCONTEXTE ENTREPRISE ACTIVE : company_id = '{company_id}'.\n"
        f"- Filtre TOUJOURS sur cette entreprise : employees.company_id = '{company_id}' "
        f"(ou la colonne company_id de la table, ou une jointure via employees).\n"
        f"- Utilise cette valeur exacte. N'écris JAMAIS le texte littéral <company_id> "
        f"ni un placeholder : la requête doit contenir l'UUID ci-dessus."
    )


# --- OpenAI Provider (IOpenAIProvider) ---


class OpenAIProvider:
    """Implémentation des appels LLM (OpenRouter) pour Text-to-SQL et Agent."""

    def generate_sql_from_prompt(
        self, prompt: str, schema_context: str, company_id: str | None = None
    ) -> str:
        today = date.today().isoformat()
        schema = _inject_runtime_context(schema_context, company_id)
        system_prompt = f"""
        Tu es un expert en génération de SQL PostgreSQL.
        En te basant sur le schéma de BDD suivant, génère une requête SQL (SELECT uniquement)
        pour répondre à la question de l'utilisateur.
        Ne réponds que par le code SQL, sans aucune explication.
        Aujourd'hui, nous sommes le {today}.
        {_company_scope_hint(company_id)}

        Schéma:
        {schema}
        """
        response = chat_completions_create(
            model=MODEL_COPILOT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        sql_query = (response.choices[0].message.content or "").strip()
        return _clean_generated_sql(sql_query, company_id)

    def format_answer_from_data(self, prompt: str, data: Any, sql_query: str) -> str:
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
            response = chat_completions_create(
                model=MODEL_COPILOT,
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
        conversation_context = "\n".join(
            f"{msg.get('role', '')}: {msg.get('content', '')}"
            for msg in conversation_history[-5:]
        )
        system_prompt = f"""Tu es un agent RH intelligent. Tu réponds à TROIS familles de questions :
1. Les données RH de l'entreprise (employés, paie, absences, etc.) → via SQL.
2. Les conventions collectives → via leur texte.
3. L'aide à l'utilisation du logiciel EYWAI (« comment faire X ? », « où trouver Y ? »,
   « à quoi sert tel module ? ») → via le guide produit.

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
  "requires_app_help": true/false,
  "requires_employee_search": true/false,
  "employee_query": "nom de l'employé à rechercher" ou null,
  "requires_collective_agreement": true/false,
  "collective_agreement_query": "convention collective concernée ou null si ambiguë" ou null,
  "agreement_id_if_unique": "id de la convention si une seule existe" ou null,
  "requires_data_retrieval": true/false,
  "data_retrieval_steps": ["étape 1", "étape 2", ...]
}}

Règles importantes:
1. **AIDE LOGICIEL (prioritaire)** : si l'utilisateur demande comment utiliser le logiciel,
   où se trouve une fonctionnalité, comment faire une action, à quoi sert un module / un écran /
   un bouton, ou demande de l'aide pour naviguer, active requires_app_help: true et NE déclenche
   ni recherche employé, ni convention, ni requête de données (mets les autres à false).
   Ce type de question ne nécessite jamais de clarification.
2. Si le nom d'un employé est mentionné mais semble incomplet ou ambigu, demande une clarification
3. Si la question nécessite plusieurs données (ex: "combien gagne X et Y"), prévois plusieurs étapes
4. Si la question (de données) est vague (ex: "combien d'employés"), demande de préciser (type de contrat? statut?)
5. Si la question concerne une convention collective, active requires_collective_agreement: true
6. Si plusieurs conventions existent et que la question ne précise pas laquelle, demande une clarification
7. Si une seule convention existe, utilise-la automatiquement (agreement_id_if_unique)
8. Détecte les questions sur conventions: congés, RTT, temps de travail, période d'essai, préavis, jours fériés, classifications, etc.

Exemples:
- "Comment lancer la paie ?" → requires_app_help: true
- "Où je trouve les notes de frais ?" → requires_app_help: true
- "Comment ajouter un nouvel employé ?" → requires_app_help: true
- "À quoi sert le module CSE ?" → requires_app_help: true
- "Comment un salarié demande un congé ?" → requires_app_help: true
- "Où trouver les identifiants de connexion d'un employé ?" → requires_app_help: true
- "Comment récupérer le mot de passe d'un collaborateur ?" → requires_app_help: true
- "Où est le PDF de création de compte ?" → requires_app_help: true
- "Comment gérer les prêts employeur ?" → requires_app_help: true
- "Où valider les avances et acomptes ?" → requires_app_help: true
- "Comment faire le rapprochement IJSS ?" → requires_app_help: true
- "Où suivre le contingent heures sup ?" → requires_app_help: true
- "Comment lancer une campagne participation ?" → requires_app_help: true
- "Où suivre le CET ?" → requires_app_help: true
- "Comment configurer la comptabilisation badgeuse ?" → requires_app_help: true
- "Comment générer une fiche de poste ?" → requires_app_help: true
- "Où importer la fiche de poste ?" → requires_app_help: true
- "Où configurer le modèle de fiche de poste ?" → requires_app_help: true
- "Fiche de poste dans la bibliothèque de documents" → requires_app_help: true
- "Combien gagne Jean" → requires_employee_search: true, requires_data_retrieval: true
- "Prêts employeur en cours" → requires_data_retrieval: true
- "Acomptes sur prime en attente" → requires_data_retrieval: true
- "IJSS non rapprochées ce mois" → requires_data_retrieval: true
- "Salariés proches du contingent HS" → requires_data_retrieval: true
- "Mouvements CET en attente de validation" → requires_data_retrieval: true
- "HS badgeuse en attente de validation" → requires_data_retrieval: true
- "Bulletins participation en attente de réponse" → requires_data_retrieval: true
- "Titres de séjour expirant ce mois" → requires_data_retrieval: true
- "Crédits repos compensateurs du trimestre" → requires_data_retrieval: true
- "Jours de fractionnement CP accordés" → requires_data_retrieval: true
- "Comment déclarer la carence CSE ?" → requires_app_help: true
- "Comment activer une dérogation au plafond 50 % pour une avance ?" → requires_app_help: true
- "Salariés payés par chèque" → requires_data_retrieval: true
- "Avances avec dérogation au plafond net" → requires_data_retrieval: true
- "Jours CP ancienneté accordés cette année" → requires_data_retrieval: true
- "Où valider les congés de mon équipe ?" → requires_app_help: true
- "Nombre d'employés" → needs_clarification: true (tous? CDI seulement? cadres?)
- "Combien de jours de congés payés par an ?" → requires_collective_agreement: true
- "Quelle est la durée de la période d'essai ?" → requires_collective_agreement: true
- "Congés payés selon la convention" → requires_collective_agreement: true (si plusieurs conventions, demande laquelle)
- "Que dit la convention SYNTEC sur les RTT ?" → requires_collective_agreement: true, collective_agreement_query: "SYNTEC"

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""

        try:
            response = chat_completions_create(
                model=MODEL_COPILOT,
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

    def answer_app_usage_question(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        feature_guide: str = APP_FEATURE_GUIDE,
    ) -> str:
        conversation_context = "\n".join(
            f"{msg.get('role', '')}: {msg.get('content', '')}"
            for msg in conversation_history[-5:]
        )
        system_prompt = f"""Tu es l'assistant intégré du logiciel RH EYWAI. Tu aides les
utilisateurs (gestionnaires RH et salariés) à se servir du logiciel : où trouver une
fonctionnalité, comment réaliser une action, à quoi sert un module ou un écran.

Tu disposes du guide officiel des fonctionnalités et de la navigation ci-dessous.

--- GUIDE DES FONCTIONNALITÉS EYWAI ---
{feature_guide}
--- FIN DU GUIDE ---

{f"Historique de conversation récent:{chr(10)}{conversation_context}{chr(10)}" if conversation_context else ""}
Règles de réponse:
- Réponds en français, de manière claire, concise et orientée action.
- Donne le chemin de navigation exact en t'appuyant sur les libellés du guide
  (ex. « Menu latéral → EYWAI Paie → Notes de frais »).
- Précise si la fonctionnalité concerne l'espace RH ou l'espace collaborateur.
- Quand c'est utile, liste les étapes à suivre sous forme de courte liste numérotée.
- Pour les titres de section (ex. Côté RH, Chemin alternatif), utilise le gras
  avec la syntaxe **Titre :** — les astérisques ne seront pas affichées, seul le
  gras le sera. N'utilise pas d'autre syntaxe Markdown (pas de #, pas de listes à
  puces avec *, pas d'italique avec un seul astérisque).
- Ne mentionne JAMAIS de détails techniques (routes /url, code, tables).
- N'invente aucune fonctionnalité, bouton ou écran absent du guide. Si la demande
  ne correspond à rien dans le guide, dis-le honnêtement et oriente vers le module
  Support."""

        try:
            response = chat_completions_create(
                model=MODEL_COPILOT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error("Erreur lors de la réponse d'aide logiciel: %s", e)
            return (
                "Je rencontre des difficultés pour répondre à votre question sur "
                "l'utilisation du logiciel. Pouvez-vous reformuler ?"
            )

    def generate_sql_for_step(
        self, step_description: str, context: Dict[str, Any]
    ) -> str:
        company_id = context.get("company_id")
        schema = _inject_runtime_context(DATABASE_SCHEMA_AGENT, company_id)
        system_prompt = f"""Tu es un expert en génération de SQL PostgreSQL.
Génère une requête SQL SELECT pour: {step_description}

Contexte: {json.dumps(context, default=str)}
{_company_scope_hint(company_id)}

Schéma de la base de données:
{schema}

Date actuelle: {date.today().isoformat()}

Réponds UNIQUEMENT avec la requête SQL, sans ```sql ni explication."""

        response = chat_completions_create(
            model=MODEL_COPILOT,
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0,
        )
        sql_query = (response.choices[0].message.content or "").strip()
        return _clean_generated_sql(sql_query, company_id)

    def answer_collective_agreement_question(
        self, prompt: str, agreement: Dict[str, Any], plan: Dict[str, Any]
    ) -> str:
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
{f"📝 **Description : {agreement_description}**" if agreement_description else ""}

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
            response = chat_completions_create(
                model=MODEL_COPILOT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error(
                "Erreur lors de la réponse sur la convention collective: %s", e
            )
            return f"Je rencontre des difficultés pour répondre à votre question sur la convention collective. Erreur: {str(e)}"

    def synthesize_final_answer(
        self,
        prompt: str,
        plan: Dict[str, Any],
        retrieval_results: List[Dict[str, Any]],
    ) -> str:
        results_summary = []
        for i, result in enumerate(retrieval_results):
            if result.get("success"):
                results_summary.append(
                    f"Étape {i + 1} - SQL: {result.get('sql')}\nDonnées: "
                    f"{json.dumps(result.get('data'), default=str, ensure_ascii=False)}"
                )
            else:
                results_summary.append(f"Étape {i + 1} - Erreur: {result.get('error')}")
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
            response = chat_completions_create(
                model=MODEL_COPILOT,
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
        self,
        name_query: str,
        threshold: float = 0.6,
        company_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        try:
            all_employees = get_employees_for_fuzzy_search(company_id)
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
                    SequenceMatcher(
                        None, query_lower, f"{last_name} {first_name}"
                    ).ratio(),
                ]
                max_similarity = max(similarities)
                if max_similarity >= threshold:
                    matches.append(
                        {
                            "employee": emp,
                            "similarity": max_similarity,
                            "full_name": f"{emp.get('first_name')} {emp.get('last_name')}",
                        }
                    )
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
