# Request schemas — payroll / simulation

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ArretTypeSimulation = Literal[
    "maladie_simple",
    "accident_travail",
    "maladie_professionnelle",
    "accident_trajet",
    "mi_temps_therapeutique",
    "ald",
    "rechute_at",
    "arret_exceptionnel",
]


class SimulationArretMaladieRequest(BaseModel):
    """Entrée POST /api/simulation/arret-maladie."""

    employee_id: str
    duree_jours: int = Field(ge=1, le=90)
    arret_type: ArretTypeSimulation
    subrogation_active: bool = True
    date_debut: date
    nombre_enfants: int = Field(default=0, ge=0, le=10)
