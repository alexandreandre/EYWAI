"""
Ports (interfaces) du domaine copilot.

L'application dépend de ces abstractions ; l'infrastructure les implémente.
Aucune dépendance à FastAPI, DB ou détails techniques.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class IOpenAIProvider(Protocol):
    """Fournit la planification, la synthèse et les réponses documentaires."""

    def analyze_intent_and_plan(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        company_agreements_summary: str,
    ) -> Dict[str, Any]:
        """Analyse l'intention et retourne un plan (intent, clarification, steps, etc.)."""
        ...

    def answer_collective_agreement_question(
        self, prompt: str, agreement: Dict[str, Any], plan: Dict[str, Any]
    ) -> str:
        """Répond à une question sur une convention collective à partir de son texte."""
        ...

    def answer_app_usage_question(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        feature_guide: str,
    ) -> str:
        """Répond à une question d'aide à l'utilisation du logiciel via le guide produit."""
        ...

    def synthesize_final_answer(
        self, prompt: str, plan: Dict[str, Any], retrieval_results: List[Dict[str, Any]]
    ) -> str:
        """Synthétise les résultats en réponse finale."""
        ...


class IEmployeeSearch(Protocol):
    """Recherche floue d'employés par nom."""

    def fuzzy_search_by_name(
        self,
        name_query: str,
        company_id: str,
        threshold: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """Retourne les employés de l'entreprise active correspondant au nom."""
        ...


class ICollectiveAgreementProvider(Protocol):
    """Fournit les conventions collectives assignées à une entreprise avec texte en cache."""

    def get_company_agreements(self, company_id: str) -> List[Dict[str, Any]]:
        """Retourne la liste des conventions avec full_text si disponible."""
        ...


class IUserCompanyResolver(Protocol):
    """Résout le company_id à partir de l'utilisateur connecté."""

    def get_company_id_for_user(self, user_id: str) -> Optional[str]:
        """Retourne le company_id du profil utilisateur ou None."""
        ...
