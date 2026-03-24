"""
Schémas de requête API pour bonus_types.

Migrés depuis schemas.bonus_type ; comportement identique.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.bonus_types.domain.enums import BonusTypeKind


class BonusTypeCreate(BaseModel):
    """Modèle pour créer une prime dans le catalogue"""

    libelle: str = Field(..., min_length=1, max_length=255)
    type: BonusTypeKind
    montant: float = Field(..., ge=0)
    seuil_heures: Optional[float] = Field(None, ge=0)
    soumise_a_cotisations: bool = True
    soumise_a_impot: bool = True
    prompt_ia: Optional[str] = None

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


class BonusTypeUpdate(BaseModel):
    """Modèle pour mettre à jour une prime"""

    libelle: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[BonusTypeKind] = None
    montant: Optional[float] = Field(None, ge=0)
    seuil_heures: Optional[float] = Field(None, ge=0)
    soumise_a_cotisations: Optional[bool] = None
    soumise_a_impot: Optional[bool] = None
    prompt_ia: Optional[str] = None
