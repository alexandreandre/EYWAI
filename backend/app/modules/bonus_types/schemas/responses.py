"""
Schémas de réponse API pour bonus_types.

Migrés depuis schemas.bonus_type ; comportement identique.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.bonus_types.domain.enums import BonusTypeKind


class BonusType(BaseModel):
    """Modèle pour une prime du catalogue entreprise"""

    id: Optional[UUID] = None
    company_id: UUID
    libelle: str = Field(..., min_length=1, max_length=255)
    type: BonusTypeKind
    montant: float = Field(..., ge=0)
    seuil_heures: Optional[float] = Field(None, ge=0)
    soumise_a_cotisations: bool = True
    soumise_a_impot: bool = True
    prompt_ia: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    @field_validator("seuil_heures")
    @classmethod
    def validate_seuil_heures(cls, v, info):
        """Valide que seuil_heures est présent si type = selon_heures"""
        if info.data.get("type") == BonusTypeKind.SELON_HEURES:
            if v is None:
                raise ValueError("seuil_heures est requis pour le type 'selon_heures'")
        elif v is not None:
            raise ValueError(
                "seuil_heures ne doit être renseigné que pour le type 'selon_heures'"
            )
        return v

    model_config = ConfigDict(
        json_encoders={
            UUID: str,
        }
    )


class BonusCalculationResultResponse(BaseModel):
    """Résultat du calcul de montant (GET /api/bonus-types/calculate/{id})"""

    amount: float
    calculated: bool
    total_hours: Optional[float] = None
    seuil: Optional[float] = None
    condition_met: Optional[bool] = None
