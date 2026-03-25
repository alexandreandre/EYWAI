"""
Ports (interfaces) du domaine companies.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ICompanyRepository(ABC):
    """Accès à la table companies (lecture / écriture settings)."""

    @abstractmethod
    def get_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne une entreprise par id (tous champs)."""
        ...

    @abstractmethod
    def get_settings(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retourne les settings d'une entreprise (colonne settings)."""
        ...

    @abstractmethod
    def update_settings(self, company_id: str, settings: Dict[str, Any]) -> None:
        """Met à jour la colonne settings pour une entreprise."""
        ...


class ICompanyDetailsProvider(ABC):
    """
    Lecture des données nécessaires au détail entreprise et KPIs
    (company + employees + payslips, company_id depuis profil).
    Implémentation dans infrastructure/queries.py.
    """

    @abstractmethod
    def get_company_with_employees_and_payslips(
        self, company_id: str
    ) -> Dict[str, Any]:
        """
        Retourne company_data, employees, payslips pour le calcul des KPIs.
        Clés : company_data (dict | None), employees (list), payslips (list).
        """
        ...

    @abstractmethod
    def get_company_id_from_profile(self, user_id: str) -> Optional[str]:
        """Retourne le company_id du profil utilisateur (table profiles)."""
        ...
