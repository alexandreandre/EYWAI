"""
Ports (interfaces) du domaine promotions.

Définitions pour repository, providers et mise à jour employé ; implémentations en infrastructure.
Aucune dépendance à FastAPI ni aux schémas API.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol

from app.modules.promotions.domain.enums import PromotionStatus, PromotionType, RhAccessRole


class PromotionApplyProtocol(Protocol):
    """Protocol pour appliquer les changements d'une promotion (évite dépendance aux schémas)."""

    @property
    def id(self) -> str: ...

    @property
    def employee_id(self) -> str: ...

    @property
    def new_job_title(self) -> Optional[str]: ...

    @property
    def new_salary(self) -> Optional[Dict[str, Any]]: ...

    @property
    def new_statut(self) -> Optional[str]: ...

    @property
    def new_classification(self) -> Optional[Dict[str, Any]]: ...

    @property
    def grant_rh_access(self) -> bool: ...

    @property
    def new_rh_access(self) -> Optional[RhAccessRole]: ...


class IPromotionRepository(ABC):
    """Port pour la persistance des promotions (lecture + écriture)."""

    @abstractmethod
    def get_by_id(self, promotion_id: str, company_id: str) -> Any:
        """Retourne une promotion complète ou None."""
        ...

    @abstractmethod
    def list(
        self,
        company_id: str,
        *,
        year: Optional[int] = None,
        status: Optional[PromotionStatus] = None,
        promotion_type: Optional[PromotionType] = None,
        employee_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Any]:
        """Liste des promotions avec filtres (jointures employé, profils)."""
        ...

    @abstractmethod
    def create(
        self,
        data: Dict[str, Any],
        company_id: str,
        requested_by: str,
    ) -> str:
        """Crée une promotion ; retourne l'id créé."""
        ...

    @abstractmethod
    def update(
        self,
        promotion_id: str,
        company_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Met à jour une promotion (champs fournis dans data)."""
        ...

    @abstractmethod
    def delete(self, promotion_id: str, company_id: str) -> None:
        """Supprime une promotion."""
        ...


class IPromotionDocumentProvider(ABC):
    """Port pour la génération et le stockage des documents PDF de promotion."""

    @abstractmethod
    def generate_letter(
        self,
        promotion_data: Dict[str, Any],
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        logo_path: Optional[str] = None,
    ) -> bytes:
        ...

    @abstractmethod
    def save_document(
        self,
        promotion_id: str,
        company_id: str,
        employee_id: str,
        employee_folder_name: str,
        pdf_bytes: bytes,
    ) -> str:
        """Sauvegarde le PDF ; retourne l'URL signée."""
        ...

    @abstractmethod
    def get_pdf_stream(self, promotion_id: str, company_id: str) -> Any:
        """Retourne un stream (BytesIO) du PDF pour téléchargement."""
        ...


class IPromotionQueries(ABC):
    """Port pour les requêtes agrégées (stats, accès RH employé)."""

    @abstractmethod
    def get_promotion_stats(
        self,
        company_id: str,
        year: Optional[int] = None,
    ) -> Any:
        """Statistiques des promotions (total, par mois, taux approbation, etc.)."""
        ...

    @abstractmethod
    def get_employee_rh_access(
        self,
        employee_id: str,
        company_id: str,
    ) -> Any:
        """Accès RH actuel d'un employé et rôles disponibles."""
        ...


class IEmployeeUpdater(ABC):
    """Port pour appliquer les effets d'une promotion (employé, accès RH)."""

    @abstractmethod
    def apply_promotion_changes(
        self,
        promotion: PromotionApplyProtocol,
        company_id: str,
    ) -> None:
        """Applique les changements de la promotion à l'employé et aux accès RH."""
        ...

    @abstractmethod
    def update_employee_rh_access(
        self,
        employee_id: str,
        company_id: str,
        new_rh_access: RhAccessRole,
        promotion_id: str,
    ) -> None:
        """Met à jour les accès RH d'un employé (création ou mise à jour user_company_accesses)."""
        ...


__all__ = [
    "PromotionApplyProtocol",
    "IPromotionRepository",
    "IPromotionDocumentProvider",
    "IPromotionQueries",
    "IEmployeeUpdater",
]
