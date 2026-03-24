"""
Ports (interfaces) du module participation.

L'infrastructure implémente ces interfaces ; l'application ne dépend que des abstractions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from app.modules.participation.domain.entities import ParticipationSimulation


class IParticipationSimulationRepository(Protocol):
    """Accès persistance aux simulations (table participation_simulations)."""

    def create(self, data: Dict[str, Any], created_by: str) -> ParticipationSimulation:
        """Crée une simulation ; data contient les champs métier + company_id, year, simulation_name."""
        ...

    def get_by_id(self, simulation_id: str, company_id: str) -> Optional[ParticipationSimulation]:
        """Retourne une simulation par id si elle appartient à l'entreprise."""
        ...

    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
    ) -> List[ParticipationSimulation]:
        """Liste les simulations de l'entreprise, optionnellement filtrées par année."""
        ...

    def delete(self, simulation_id: str, company_id: str) -> bool:
        """Supprime une simulation si elle appartient à l'entreprise. Retourne True si supprimée."""
        ...

    def exists_with_name(self, company_id: str, year: int, simulation_name: str) -> bool:
        """Vérifie si une simulation avec ce nom existe déjà pour l'année."""
        ...


class IEmployeeParticipationDataProvider(Protocol):
    """
    Fournit les données employés pour le simulateur : salaire annuel, jours de présence, ancienneté.

    Source actuelle : tables profiles, employees, employee_schedules, payslips.
    À implémenter en infrastructure (queries/repository).
    """

    def get_employee_participation_data(
        self,
        company_id: str,
        year: int,
    ) -> List[Dict[str, Any]]:
        """
        Retourne une liste de dicts avec pour chaque employé :
        employee_id, first_name, last_name, annual_salary, presence_days,
        seniority_years, has_real_salary, has_real_presence.
        """
        ...
