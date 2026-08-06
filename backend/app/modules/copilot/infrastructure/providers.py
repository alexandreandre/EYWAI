"""
Providers infrastructure : LLM (OpenRouter), recherche employés, conventions collectives, résolution company.

Implémentent les interfaces du domaine pour le Copilot à outils RH fermés.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List

from app.shared.infrastructure.ai import (
    MODEL_COPILOT_AGREEMENT,
    MODEL_COPILOT_APP_HELP,
    MODEL_COPILOT_PLANNING,
    MODEL_COPILOT_SYNTHESIS,
    chat_completions_create,
)
from app.modules.copilot.domain.agreement_context import construire_contexte
from app.modules.copilot.infrastructure.app_knowledge import APP_FEATURE_GUIDE
from app.modules.copilot.infrastructure.queries import (
    get_company_collective_agreements as queries_get_company_agreements,
    get_company_id_for_user as queries_get_company_id,
    get_employees_for_fuzzy_search,
)

_INTERNAL_IDENTIFIER_KEYS = frozenset(
    {"id", "company_id", "employee_id", "group_id", "team_id"}
)


def _sanitize_for_llm(value: Any) -> Any:
    """Retire récursivement les identifiants internes avant envoi au fournisseur."""
    if isinstance(value, dict):
        return {
            key: _sanitize_for_llm(item)
            for key, item in value.items()
            if key not in _INTERNAL_IDENTIFIER_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_for_llm(item) for item in value]
    return value


# --- OpenAI Provider (IOpenAIProvider) ---


class OpenAIProvider:
    """Implémentation des appels LLM de planification et de synthèse."""

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
1. Les données RH de l'entreprise (employés, paie, absences, etc.) → via les outils autorisés.
2. Les conventions collectives → via leur texte.
3. L'aide à l'utilisation du logiciel EYWAI (« comment faire X ? », « où trouver Y ? »,
   « à quoi sert tel module ? ») → via le guide produit.

Date actuelle: {date.today().isoformat()}

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
  "requires_collective_agreement": true/false,
  "collective_agreement_query": "convention collective concernée ou null si ambiguë" ou null,
  "agreement_id_if_unique": "id de la convention si une seule existe" ou null,
  "requires_data_retrieval": true/false,
  "data_tool_calls": [
    {{"tool": "<nom_outil_autorisé>", "arguments": {{...}}}}
  ]
}}

CATALOGUE FERMÉ D'OUTILS DE DONNÉES (aucun autre n'existe) :
- "employee_count" — compte les salariés.
  arguments optionnels: {{"employment_status": "actif"|"active"|"en_sortie"|"en_onboarding"|"parti"|"inactif",
  "contract_type": "CDI"|"CDD"|…}}.
- "employee_search" — recherche un salarié par nom.
  arguments: {{"name": "<nom>"}} + employment_status, contract_type, limit (optionnels).
- "payroll_summary" — synthèse paie d'une période. arguments: {{"period": "AAAA-MM"}} (optionnel, défaut mois courant).
- "absence_summary" — synthèse des absences.
  arguments optionnels: {{"status": "<statut>", "type": "<type>",
  "date_start": "AAAA-MM-JJ", "date_end": "AAAA-MM-JJ"}} (borne sur selected_days).
  status ∈ {{"pending", "validated", "rejected", "cancelled"}}.
  type ∈ {{"conge_paye", "rtt", "sans_solde", "repos_compensateur",
  "evenement_familial", "arret_maladie", "arret_at", "arret_paternite",
  "arret_maternite", "arret_maladie_pro"}}. N'invente aucune autre valeur.
- "planning_summary" — synthèse du planning. arguments: {{"date_start": "AAAA-MM-JJ", "date_end": "AAAA-MM-JJ"}} (optionnels).
- "hr_indicators" — indicateurs RH (turnover, absentéisme, effectifs). arguments: {{}}.

RÈGLES STRICTES POUR data_tool_calls :
- N'utilise QUE des outils de cette liste. N'invente jamais d'outil.
- Ne fournis JAMAIS d'identifiant d'entreprise (company_id), de groupe (group_id),
  d'identifiants internes de salariés (employee_ids), ni de SQL / nom de table /
  requête brute : ces valeurs sont imposées côté serveur.
- Au plus 5 appels d'outils. Laisse "data_tool_calls" vide si aucune donnée n'est nécessaire.
- Si la question exige des données hors catalogue (salaire individuel, titre de séjour,
  avance/prêt, note de frais détaillée…), NE PAS inventer d'outil : mets
  requires_data_retrieval: false et needs_clarification: true avec une question
  qui propose ce que tu PEUX faire (effectifs, synthèse paie, absences, indicateurs).

Règles importantes:
1. **AIDE LOGICIEL (prioritaire)** : si l'utilisateur demande comment utiliser le logiciel,
   où se trouve une fonctionnalité, comment faire une action, à quoi sert un module / un écran /
   un bouton, ou demande de l'aide pour naviguer, active requires_app_help: true et NE déclenche
   ni recherche employé, ni convention, ni requête de données (mets les autres à false).
   Ce type de question ne nécessite jamais de clarification.
2. Si le nom d'un employé est mentionné mais semble incomplet ou ambigu, demande une clarification.
   Sinon utilise l'outil employee_search avec le nom dans son argument "name".
3. Si la question nécessite plusieurs données, prévois plusieurs appels d'outils autorisés
4. Ne demande une précision QUE si la réponse serait trompeuse sans elle. Une question
   d'effectif sans précision ("combien de salariés ?", "combien de personnes travaillent
   ici ?") se répond sur l'effectif ACTIF (employee_count avec employment_status: "actif") :
   la réponse proposera d'affiner. Ne renvoie pas une question quand une réponse utile existe.
5. Si la question concerne une convention collective, active requires_collective_agreement: true
6. Si plusieurs conventions existent et que la question ne précise pas laquelle, demande une clarification
7. Si une seule convention existe, utilise-la automatiquement (agreement_id_if_unique)
9. Si le résumé ci-dessus indique qu'AUCUNE convention n'est assignée à l'entreprise et que
   la question porte sur la convention, active quand même requires_collective_agreement: true :
   l'utilisateur recevra une réponse claire sur l'absence de convention. Ne demande pas de
   clarification dans ce cas — il n'y a rien à clarifier.
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
- "Comment déclarer la carence CSE ?" → requires_app_help: true
- "Comment activer une dérogation au plafond 50 % pour une avance ?" → requires_app_help: true
- "Où valider les congés de mon équipe ?" → requires_app_help: true
- "Comment restreindre les droits d'un RH à une équipe ?" → requires_app_help: true
- "Où activer le forfait jours d'un salarié ?" → requires_app_help: true
- "Où créer / générer les plans de calendriers 2026 ?" → requires_app_help: true
- "Où paramétrer les pauses payées / non payées ?" → requires_app_help: true
- "Comment connecter Cegid Loop / l'intégration comptable ?" → requires_app_help: true
- "Comment télécharger le contrat en Word ?" → requires_app_help: true
- "Comment basculer Vue RH / Vue Collaborateur ?" → requires_app_help: true
- "On me force à changer mon mot de passe à la connexion" → requires_app_help: true
- "Cherche Jean Dupont" → requires_data_retrieval: true, outil employee_search
- "Combien de salariés actifs ?" → requires_data_retrieval: true, outil employee_count (employment_status: actif)
- "Combien de CDI ?" → requires_data_retrieval: true, outil employee_count (contract_type: CDI)
- "Combien de salariés en onboarding ?" → requires_data_retrieval: true, outil employee_count (employment_status: en_onboarding)
- "Synthèse paie de 2026-07" → requires_data_retrieval: true, outil payroll_summary
- "Absences validées ce mois" → requires_data_retrieval: true, outil absence_summary (+ date_start/date_end)
- "Planning du 20 juillet" → requires_data_retrieval: true, outil planning_summary
- "Quel est le turnover ?" → requires_data_retrieval: true, outil hr_indicators
- "Nombre d'employés" → needs_clarification: true (tous? CDI seulement? actifs? onboarding?)
- "Quel est le salaire de Martin ?" → needs_clarification: true (hors catalogue : propose recherche du salarié ou synthèse paie)
- "Combien de jours de congés payés par an ?" → requires_collective_agreement: true
- "Quelle est la durée de la période d'essai ?" → requires_collective_agreement: true
- "Congés payés selon la convention" → requires_collective_agreement: true (si plusieurs conventions, demande laquelle)
- "Que dit la convention SYNTEC sur les RTT ?" → requires_collective_agreement: true, collective_agreement_query: "SYNTEC"

Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""

        try:
            response = chat_completions_create(
                model=MODEL_COPILOT_PLANNING,
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
            # Fail-closed : en cas d'échec de parsing du plan, on NE tente JAMAIS
            # une requête de données générique (aucun repli SQL). On désactive la
            # récupération de données et on renvoie un marqueur d'erreur.
            return {
                "intent": "Unknown",
                "needs_clarification": False,
                "requires_app_help": False,
                "requires_collective_agreement": False,
                "requires_data_retrieval": False,
                "data_tool_calls": [],
                "error": "plan_parse_failed",
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
                model=MODEL_COPILOT_APP_HELP,
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

    def _choisir_sections(self, question: str, sommaire: str) -> set[int]:
        """Demande au modèle quelles sections du sommaire lire pour la question.

        Franchit la barrière de vocabulaire entre la question d'une gestionnaire
        RH et les intitulés d'une convention collective : « combien de jours pour
        un mariage » ne partage aucun mot avec « Congés payés. Congés
        exceptionnels ». Appel court et bon marché (le sommaire seul).

        En cas d'échec, on renvoie un ensemble vide : la sélection lexicale
        reprend la main, on ne bloque jamais la réponse.
        """
        if not sommaire:
            return set()
        system_prompt = (
            "Tu reçois le sommaire numéroté d'une convention collective et une "
            "question RH. Indique les numéros des sections à lire pour y "
            "répondre.\n"
            "- Sois large plutôt qu'étroit : une section de trop ne coûte rien, "
            "une section manquante empêche la réponse.\n"
            "- Retiens entre 1 et 12 numéros, du plus pertinent au moins "
            "pertinent.\n"
            "- Réponds UNIQUEMENT par un JSON de la forme "
            '{"sections": [12, 34]}, sans texte autour.'
        )
        try:
            response = chat_completions_create(
                model=MODEL_COPILOT_PLANNING,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Question : {question}\n\nSommaire :\n{sommaire}",
                    },
                ],
                temperature=0,
                max_tokens=200,
            )
            brut = (response.choices[0].message.content or "").strip()
            if brut.startswith("```"):
                brut = brut.split("\n", 1)[1].rsplit("\n", 1)[0]
                if brut.startswith("json"):
                    brut = brut[4:].strip()
            rangs = json.loads(brut).get("sections") or []
            return {int(r) for r in rangs if isinstance(r, (int, float, str)) and str(r).lstrip("-").isdigit()}
        except Exception as e:  # noqa: BLE001 - repli sur la sélection lexicale
            logging.warning("Choix des sections de convention indisponible: %s", e)
            return set()

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
        # Le texte de base d'une convention dépasse 800 000 caractères : on ne
        # tronque plus aveuglément à 150 000 (ce qui coupait la fin du document),
        # on sélectionne les sections utiles à la question — désignées à la
        # lecture du sommaire, complétées par un classement lexical — et on joint
        # toujours le sommaire complet.
        texte_convention = agreement["full_text"]
        contexte = construire_contexte(texte_convention, prompt)
        if not contexte.integral:
            rangs = self._choisir_sections(prompt, contexte.sommaire)
            if rangs:
                contexte = construire_contexte(
                    texte_convention, prompt, rangs_prioritaires=rangs
                )

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

        if contexte.integral:
            preambule = (
                f"Voici le texte intégral de la convention collective "
                f"{agreement_name} (IDCC {agreement_idcc}) :"
            )
            rappel_extrait = ""
        else:
            preambule = (
                f"Voici les sections de la convention collective {agreement_name} "
                f"(IDCC {agreement_idcc}) les plus proches de la question "
                f"({contexte.caracteres_retenus} caractères retenus sur "
                f"{contexte.caracteres_source}) :"
            )
            rappel_extrait = (
                "\n- Le texte ci-dessus est un EXTRAIT sélectionné. Si la réponse "
                "devrait se trouver dans une section listée au sommaire mais non "
                "reproduite ici, dis-le explicitement au lieu de conclure que la "
                "convention est muette."
            )

        sommaire_bloc = (
            f"\n**Sommaire complet de la convention :**\n{contexte.sommaire}\n"
            if contexte.sommaire
            else ""
        )

        user_prompt = f"""{preambule}

---
{contexte.texte}
---
{sommaire_bloc}
**Question de l'utilisateur :**
{prompt}

**Instructions :**
Réponds à cette question en te basant sur le texte de la convention collective ci-dessus. Cite les articles ou sections pertinents et structure ta réponse de manière claire et professionnelle.{rappel_extrait}"""

        try:
            response = chat_completions_create(
                model=MODEL_COPILOT_AGREEMENT,
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
            return (
                "Je rencontre des difficultés pour répondre à votre question "
                "sur la convention collective. Veuillez réessayer."
            )

    def synthesize_final_answer(
        self,
        prompt: str,
        plan: Dict[str, Any],
        retrieval_results: List[Dict[str, Any]],
        sources: List[tuple[str, str]] | None = None,
    ) -> str:
        results_summary = []
        for i, result in enumerate(retrieval_results):
            if result.get("success"):
                sanitized_data = _sanitize_for_llm(result.get("data"))
                results_summary.append(
                    f"Outil {result.get('tool') or i + 1} - Données: "
                    f"{json.dumps(sanitized_data, default=str, ensure_ascii=False)}"
                )
            else:
                # Le motif (filtre inconnu, outil indisponible) est utile à la
                # réponse : il évite de faire passer une absence de données pour
                # une absence de faits.
                results_summary.append(
                    f"Outil {result.get('tool') or i + 1} sans résultat : "
                    f"{result.get('error') or 'indisponible'}"
                )
        results_text = "\n\n".join(results_summary)

        sources_text = "\n\n".join(
            f"### {titre}\n{contenu}" for titre, contenu in (sources or []) if contenu
        )
        bloc_sources = (
            "\n\nRéponses déjà rédigées sur les autres volets de la question "
            "(à intégrer, sans les réécrire ni les contredire) :\n"
            f"{sources_text}\n"
            if sources_text
            else ""
        )

        system_prompt = f"""Tu es un assistant RH professionnel et convivial, expert en données RH et en conventions collectives.

Question de l'utilisateur: {prompt}

Plan d'action: {json.dumps(_sanitize_for_llm(plan), ensure_ascii=False)}

Résultats des outils autorisés:
{results_text}{bloc_sources}

Date actuelle: {date.today().isoformat()}

Génère une réponse claire, professionnelle et concise en français.
- Utilise des phrases complètes et naturelles
- Mets en avant les informations importantes
- Si plusieurs employés sont mentionnés, structure ta réponse clairement
- Si des données manquent, explique-le poliment
- Ajoute du contexte si utile (ex: "Ce qui représente X% du salaire total")
- Si la question comporte plusieurs volets (chiffres de l'entreprise ET règle
  conventionnelle, par exemple), traite-les TOUS, chacun sous son propre
  intertitre. Ne laisse jamais un volet sans réponse au motif que l'autre source
  ne le couvrait pas : les chiffres viennent des outils, la règle vient de la
  convention.
- Les volets déjà rédigés ci-dessous s'appuient sur des textes officiels :
  reprends-les SANS AJOUTER une règle, une durée ou un chiffre qui n'y figure
  pas, et conserve leurs réserves (« non précisé dans le texte », « à vérifier
  dans l'avenant »). Tu peux les raccourcir, jamais les compléter de mémoire.
- Respecte scrupuleusement la période des chiffres d'absence : « total_demandes »
  compte des DEMANDES, pas des personnes, et « periode » dit sur quoi elles
  portent. N'écris « actuellement » ou « en ce moment » que pour
  « salaries_absents_aujourdhui ». Un décompte sur tout l'historique ne décrit
  jamais la situation du jour.
- Si la question concerne des éléments qui pourraient être régis par une convention collective (congés, RTT, période d'essai, etc.), mentionne-le et suggère de consulter la convention collective de l'entreprise pour plus de détails

Ne mentionne JAMAIS les détails techniques internes (outils, SQL, tables).
Ne signe pas la réponse et n'ajoute aucune formule de politesse finale du type
« Cordialement » ou « [Votre Nom] » : tu es un assistant intégré, pas un courrier.
Si les résultats ne couvrent pas la question (données absentes ou hors périmètre
des outils), dis-le clairement et propose ce que tu peux fournir à la place.
Réponds comme un collègue RH serviable et expert."""

        try:
            response = chat_completions_create(
                model=MODEL_COPILOT_SYNTHESIS,
                messages=[{"role": "system", "content": system_prompt}],
                temperature=0.7,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logging.error("Erreur lors de la synthèse: %s", e)
            return "Je rencontre des difficultés pour synthétiser ces informations. Pouvez-vous reformuler votre question ?"


# --- Employee search (IEmployeeSearch) ---


class EmployeeSearchProvider:
    """Recherche floue d'employés par nom, scopée à l'entreprise serveur."""

    def fuzzy_search_by_name(
        self,
        name_query: str,
        company_id: str,
        threshold: float = 0.6,
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
