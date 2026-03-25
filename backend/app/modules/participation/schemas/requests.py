"""
Schémas de requête API pour participation (Participation & Intéressement).

Migrés depuis api/routers/participation.py — comportement identique (str + pattern).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ParticipationSimulationCreate(BaseModel):
    """Modèle pour créer une simulation de participation"""

    year: int = Field(..., ge=2020, le=2100)
    simulation_name: str = Field(..., min_length=1, max_length=255)

    # Données entreprise
    benefice_net: float
    capitaux_propres: float
    salaires_bruts: float
    valeur_ajoutee: float

    # Paramètres Participation
    participation_mode: str = Field(
        ..., pattern="^(uniforme|salaire|presence|combinaison)$"
    )
    participation_salaire_percent: int = Field(default=50, ge=0, le=100)
    participation_presence_percent: int = Field(default=50, ge=0, le=100)

    # Paramètres Intéressement
    interessement_enabled: bool = False
    interessement_envelope: Optional[float] = None
    interessement_mode: Optional[str] = Field(
        None, pattern="^(uniforme|salaire|presence|combinaison)$"
    )
    interessement_salaire_percent: int = Field(default=50, ge=0, le=100)
    interessement_presence_percent: int = Field(default=50, ge=0, le=100)

    # Résultats
    results_data: Dict[str, Any] = Field(default_factory=dict)
