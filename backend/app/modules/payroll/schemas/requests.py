# Request schemas — payroll / simulation

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

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


StatutSimulation = Literal["Cadre", "Non-Cadre"]


class SimulationArretMaladieRequest(BaseModel):
    """Entrée POST /api/simulation/arret-maladie."""

    employee_id: str
    duree_jours: int = Field(ge=1, le=365)
    arret_type: ArretTypeSimulation
    subrogation_active: bool = True
    date_debut: date
    nombre_enfants: int = Field(default=0, ge=0, le=10)

    # Overrides « what-if » optionnels : modifient le calcul sans toucher la fiche salarié.
    salaire_base_override: Optional[float] = Field(default=None, ge=0)
    statut_override: Optional[StatutSimulation] = None
    anciennete_mois_override: Optional[int] = Field(default=None, ge=0, le=600)
