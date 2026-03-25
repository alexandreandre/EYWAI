"""
Ports (interfaces) pour le module collective_agreements.

L'infrastructure implémente ces interfaces. Aucune dépendance à FastAPI.
Contrats en dict pour rester aligné avec le comportement API actuel.
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol


class ICollectiveAgreementRepository(Protocol):
    """Accès persistance catalogue et assignations. Retourne des dict (forme API)."""

    def list_catalog(
        self,
        *,
        sector: Optional[str] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> List[dict[str, Any]]:
        """Liste les conventions du catalogue (sans rules_pdf_url)."""
        ...

    def get_catalog_item(self, agreement_id: str) -> Optional[dict[str, Any]]:
        """Récupère une convention par id (sans rules_pdf_url)."""
        ...

    def get_catalog_item_rules_path(self, agreement_id: str) -> Optional[str]:
        """Récupère uniquement rules_pdf_path pour une convention (ou None)."""
        ...

    def get_classifications_for_agreement(self, agreement_id: str) -> List[Any]:
        """Grille de classification pour une convention (via idcc)."""
        ...

    def create_catalog_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Crée une entrée catalogue."""
        ...

    def update_catalog_item(
        self, agreement_id: str, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Met à jour une entrée catalogue."""
        ...

    def delete_catalog_item(self, agreement_id: str) -> bool:
        """Supprime une entrée catalogue (sans supprimer le PDF du storage)."""
        ...

    def get_my_company_assignments(self, company_id: str) -> List[dict[str, Any]]:
        """Liste les assignations d'une entreprise avec agreement_details (sans rules_pdf_url)."""
        ...

    def assign_to_company(
        self, company_id: str, collective_agreement_id: str, assigned_by: str
    ) -> dict[str, Any]:
        """Assigne une convention à une entreprise."""
        ...

    def unassign_from_company(self, assignment_id: str, company_id: str) -> bool:
        """Retire une assignation."""
        ...

    def get_all_assignments_by_company(self) -> List[dict[str, Any]]:
        """Liste toutes les entreprises avec leurs assignations (sans rules_pdf_url)."""
        ...

    def check_assignment_exists(
        self, company_id: str, collective_agreement_id: str
    ) -> bool:
        """Vérifie qu'une convention est assignée à l'entreprise."""
        ...

    def get_agreement_for_chat(self, agreement_id: str) -> Optional[dict[str, Any]]:
        """Récupère id, name, idcc, description, rules_pdf_path pour le chat."""
        ...


class IAgreementStorageProvider(Protocol):
    """Génération d'URLs signées et suppression de fichiers (bucket collective_agreement_rules)."""

    def create_signed_url(self, path: str, ttl_seconds: int = 3600) -> Optional[str]:
        """Retourne l'URL signée de lecture pour un chemin."""
        ...

    def create_signed_upload_url(self, path: str) -> dict[str, str]:
        """Retourne path + signedUrl pour upload."""
        ...

    def remove(self, paths: List[str]) -> None:
        """Supprime un ou plusieurs fichiers du bucket."""
        ...


class IAgreementTextCache(Protocol):
    """Cache du texte extrait des PDFs (table collective_agreement_texts)."""

    def get_full_text(self, agreement_id: str) -> Optional[str]:
        """Récupère le texte en cache (full_text) ou None."""
        ...

    def set_full_text(
        self, agreement_id: str, full_text: str, character_count: int
    ) -> None:
        """Enregistre ou met à jour le cache."""
        ...

    def delete(self, agreement_id: str) -> None:
        """Supprime l'entrée de cache."""
        ...


class IAgreementPdfTextExtractor(Protocol):
    """Extraction du texte depuis une URL de PDF."""

    def extract(self, pdf_url: str) -> str:
        """Télécharge le PDF et en extrait le texte."""
        ...


class IAgreementChatProvider(Protocol):
    """Réponse à une question sur une convention (LLM)."""

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        """Retourne la réponse du LLM."""
        ...
