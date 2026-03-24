"""
Schémas de réponse API pour mutuelle_types.

Alignés sur le legacy schemas.mutuelle_type.MutuelleType.
Comportement identique. La liste GET enrichit avec employee_ids (champ optionnel ici).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MutuelleType(BaseModel):
    """Modèle pour une formule de mutuelle du catalogue entreprise"""

    id: Optional[UUID] = None
    company_id: UUID
    libelle: str = Field(..., min_length=1, max_length=255)
    montant_salarial: float = Field(..., ge=0)
    montant_patronal: float = Field(..., ge=0)
    part_patronale_soumise_a_csg: bool = True
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    employee_ids: list[str] = Field(default_factory=list)  # enrichi côté application pour GET list

    model_config = ConfigDict(
        json_encoders={UUID: str},
    )
