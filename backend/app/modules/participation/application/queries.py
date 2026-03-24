"""
Queries applicatives (read) pour participation.

Délèguent au ParticipationService. Comportement identique au routeur legacy.
Le routeur fournira company_id depuis le contexte utilisateur (profiles).
"""
from __future__ import annotations

from typing import List, Optional

from app.modules.participation.application.dto import EmployeeParticipationRow
from app.modules.participation.application.service import (
    ParticipationService,
    get_participation_service,
)
from app.modules.participation.domain.entities import ParticipationSimulation


def get_employee_participation_data(
    company_id: str,
    year: int,
    service: Optional[ParticipationService] = None,
) -> List[EmployeeParticipationRow]:
    """
    Récupère les données employés pour le simulateur (salaire annuel, présence, ancienneté).
    """
    svc = service or get_participation_service()
    return svc.get_employee_participation_data(company_id, year)


def list_participation_simulations(
    company_id: str,
    year: Optional[int] = None,
    service: Optional[ParticipationService] = None,
) -> List[ParticipationSimulation]:
    """Liste les simulations de l'entreprise, optionnellement filtrées par année."""
    svc = service or get_participation_service()
    return svc.list_simulations(company_id, year)


def get_participation_simulation(
    simulation_id: str,
    company_id: str,
    service: Optional[ParticipationService] = None,
) -> Optional[ParticipationSimulation]:
    """Récupère une simulation par id si elle appartient à l'entreprise."""
    svc = service or get_participation_service()
    return svc.get_simulation(simulation_id, company_id)
