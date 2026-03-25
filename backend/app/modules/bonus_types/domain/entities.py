"""
Entité domaine : prime du catalogue entreprise (BonusType).

Alignée sur la table company_bonus_types et le legacy schemas.bonus_type.BonusType.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.modules.bonus_types.domain.enums import BonusTypeKind


@dataclass(frozen=False)
class BonusType:
    """Prime du catalogue entreprise."""

    id: Optional[UUID]
    company_id: UUID
    libelle: str
    type: BonusTypeKind
    montant: float
    seuil_heures: Optional[float]
    soumise_a_cotisations: bool
    soumise_a_impot: bool
    prompt_ia: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
