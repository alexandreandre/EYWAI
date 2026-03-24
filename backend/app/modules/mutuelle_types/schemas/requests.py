"""
Schémas de requête API pour mutuelle_types.

Alignés sur le legacy schemas.mutuelle_type (MutuelleTypeCreate, MutuelleTypeUpdate).
Comportement identique à conserver lors de la migration.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MutuelleTypeCreate(BaseModel):
    """Modèle pour créer une formule de mutuelle dans le catalogue"""

    libelle: str = Field(..., min_length=1, max_length=255)
    montant_salarial: float = Field(..., ge=0)
    montant_patronal: float = Field(..., ge=0)
    part_patronale_soumise_a_csg: bool = True
    is_active: bool = True
    employee_ids: List[str] = Field(default_factory=list)


class MutuelleTypeUpdate(BaseModel):
    """Modèle pour mettre à jour une formule de mutuelle"""

    libelle: str | None = Field(None, min_length=1, max_length=255)
    montant_salarial: float | None = Field(None, ge=0)
    montant_patronal: float | None = Field(None, ge=0)
    part_patronale_soumise_a_csg: bool | None = None
    is_active: bool | None = None
    employee_ids: List[str] | None = None
