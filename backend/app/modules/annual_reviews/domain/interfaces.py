"""
Ports du domaine annual_reviews.

Implémentations dans infrastructure/. Pas de dépendance FastAPI ni DB ici.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IAnnualReviewRepository(ABC):
    """Accès à la table annual_reviews (CRUD + listes)."""

    @abstractmethod
    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les entretiens de l'entreprise (avec jointure employees pour liste RH)."""
        ...

    @abstractmethod
    def get_by_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un entretien par id."""
        ...

    @abstractmethod
    def list_by_employee(
        self, employee_id: str, company_id: str
    ) -> List[Dict[str, Any]]:
        """Liste les entretiens d'un employé."""
        ...

    @abstractmethod
    def get_my_current(
        self, employee_id: str, company_id: str, year: int
    ) -> Optional[Dict[str, Any]]:
        """Entretien de l'année donnée pour un employé (ex. année courante)."""
        ...

    @abstractmethod
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un entretien, retourne la ligne insérée."""
        ...

    @abstractmethod
    def update(self, review_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Met à jour un entretien, retourne la ligne mise à jour."""
        ...

    @abstractmethod
    def delete(self, review_id: str) -> None:
        """Supprime un entretien."""
        ...

    @abstractmethod
    def get_employee_company_id(self, employee_id: str) -> Optional[str]:
        """Retourne le company_id de l'employé (pour validation création / liste par employé)."""
        ...

    @abstractmethod
    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Retourne les champs employé nécessaires au PDF (id, first_name, last_name, job_title)."""
        ...

    @abstractmethod
    def get_company_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne les données entreprise pour le PDF."""
        ...


class IAnnualReviewPdfGenerator(ABC):
    """Génération du PDF d'entretien annuel clôturé."""

    @abstractmethod
    def generate(
        self,
        review_data: Dict[str, Any],
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
    ) -> bytes:
        """Génère le PDF. À n'appeler que si status == 'cloture'."""
        ...
