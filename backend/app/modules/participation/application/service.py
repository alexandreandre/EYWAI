"""
Service applicatif participation (orchestration).

Délègue au repository (simulations) et aux requêtes infra (données employés).
Comportement identique au routeur legacy.
"""
from __future__ import annotations

from typing import List, Optional

from app.modules.participation.application.dto import (
    EmployeeParticipationRow,
    SimulationCreateInput,
    employee_row_from_dict,
    simulation_create_input_to_insert_data,
)
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.infrastructure.queries import (
    fetch_employee_participation_data,
)
from app.modules.participation.infrastructure.repository import (
    ParticipationSimulationRepository,
)


class DuplicateSimulationNameError(ValueError):
    """Une simulation avec ce nom existe déjà pour cette année."""

    def __init__(self, simulation_name: str, year: int) -> None:
        self.simulation_name = simulation_name
        self.year = year
        super().__init__(
            f"Une simulation avec le nom '{simulation_name}' existe déjà pour l'année {year}."
        )


class ParticipationService:
    """
    Service participation & intéressement.
    Utilise le repository et les requêtes infrastructure.
    """

    def __init__(
        self,
        simulation_repository: Optional[ParticipationSimulationRepository] = None,
    ) -> None:
        self._repo = simulation_repository or ParticipationSimulationRepository()

    def get_employee_participation_data(
        self, company_id: str, year: int
    ) -> List[EmployeeParticipationRow]:
        """Données employés pour le simulateur (salaire annuel, présence, ancienneté)."""
        rows = fetch_employee_participation_data(company_id, year)
        return [employee_row_from_dict(d) for d in rows]

    def create_simulation(
        self, input_data: SimulationCreateInput
    ) -> ParticipationSimulation:
        """Crée une simulation ; lève DuplicateSimulationNameError si le nom existe déjà."""
        if self._repo.exists_with_name(
            input_data.company_id, input_data.year, input_data.simulation_name
        ):
            raise DuplicateSimulationNameError(
                input_data.simulation_name, input_data.year
            )
        data = simulation_create_input_to_insert_data(input_data)
        return self._repo.create(data, input_data.created_by)

    def list_simulations(
        self, company_id: str, year: Optional[int] = None
    ) -> List[ParticipationSimulation]:
        """Liste les simulations de l'entreprise, optionnellement filtrées par année."""
        return self._repo.list_by_company(company_id, year)

    def get_simulation(
        self, simulation_id: str, company_id: str
    ) -> Optional[ParticipationSimulation]:
        """Récupère une simulation par id si elle appartient à l'entreprise."""
        return self._repo.get_by_id(simulation_id, company_id)

    def delete_simulation(
        self, simulation_id: str, company_id: str
    ) -> bool:
        """Supprime une simulation si elle appartient à l'entreprise. Retourne True si supprimée."""
        return self._repo.delete(simulation_id, company_id)


def get_participation_service() -> ParticipationService:
    """Factory : retourne le service avec les dépendances par défaut."""
    return ParticipationService()
