# app/modules/medical_follow_up/domain/interfaces.py
"""Interfaces du domaine (repositories, providers) pour inversion de dépendances."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IObligationRepository(ABC):
    """Port pour la persistance des obligations (lecture/écriture)."""

    @abstractmethod
    def list_for_company(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        visit_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_from: Optional[str] = None,
        due_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les obligations avec filtres (hors annulées)."""
        ...

    @abstractmethod
    def get_kpis(self, company_id: str) -> Dict[str, int]:
        """Retourne overdue_count, due_within_30_count, active_total, completed_this_month."""
        ...

    @abstractmethod
    def mark_planified(self, obligation_id: str, company_id: str, planned_date: str, justification: Optional[str]) -> None:
        """Marque une obligation comme planifiée."""
        ...

    @abstractmethod
    def mark_completed(self, obligation_id: str, company_id: str, completed_date: str, justification: Optional[str]) -> None:
        """Marque une obligation comme réalisée."""
        ...

    @abstractmethod
    def create_on_demand(self, company_id: str, employee_id: str, request_motif: str, request_date: str) -> None:
        """Crée une obligation « visite à la demande »."""
        ...

    @abstractmethod
    def list_for_employee(self, company_id: str, employee_id: str) -> List[Dict[str, Any]]:
        """Liste les obligations d’un collaborateur (hors annulées)."""
        ...


class ICompanyMedicalSettingsProvider(ABC):
    """Port pour savoir si le module suivi médical est activé pour une entreprise."""

    @abstractmethod
    def is_enabled(self, company_id: str) -> bool:
        """True si le module est activé pour l’entreprise."""
        ...
