"""
Entités du domaine participation (Participation & Intéressement).

À migrer depuis la logique actuelle du routeur legacy.
Une simulation est identifiée par id, company_id, year, simulation_name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.modules.participation.domain.enums import DistributionMode


@dataclass
class ParticipationSimulation:
    """
    Simulation de participation & intéressement (entité domaine).

    Correspond à la table participation_simulations.
    """

    id: UUID
    company_id: UUID
    year: int
    simulation_name: str
    benefice_net: float
    capitaux_propres: float
    salaires_bruts: float
    valeur_ajoutee: float
    participation_mode: DistributionMode
    participation_salaire_percent: int
    participation_presence_percent: int
    interessement_enabled: bool
    interessement_envelope: Optional[float]
    interessement_mode: Optional[DistributionMode]
    interessement_salaire_percent: int
    interessement_presence_percent: int
    results_data: Dict[str, Any]
    created_at: datetime
    created_by: Optional[UUID]
    updated_at: datetime
