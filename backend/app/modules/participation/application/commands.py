"""
Commandes applicatives (write) pour participation.

Délèguent au ParticipationService. Comportement identique au routeur legacy.
Le routeur (lorsqu'il sera branché) fournira company_id et created_by depuis le contexte utilisateur.
"""

from __future__ import annotations

from typing import Optional

from app.modules.participation.application.dto import SimulationCreateInput
from app.modules.participation.application.service import (
    DuplicateSimulationNameError,
    ParticipationService,
    get_participation_service,
)
from app.modules.participation.domain.entities import ParticipationSimulation


def create_participation_simulation(
    input_data: SimulationCreateInput,
    service: Optional[ParticipationService] = None,
) -> ParticipationSimulation:
    """
    Crée une nouvelle simulation de participation & intéressement.
    Lève DuplicateSimulationNameError si (company_id, year, simulation_name) existe déjà.
    """
    svc = service or get_participation_service()
    return svc.create_simulation(input_data)


def delete_participation_simulation(
    simulation_id: str,
    company_id: str,
    service: Optional[ParticipationService] = None,
) -> bool:
    """
    Supprime une simulation si elle appartient à l'entreprise.
    Retourne True si supprimée, False si non trouvée.
    """
    svc = service or get_participation_service()
    return svc.delete_simulation(simulation_id, company_id)


# Réexport pour les routers qui importeront depuis application
__all__ = [
    "create_participation_simulation",
    "delete_participation_simulation",
    "DuplicateSimulationNameError",
]
