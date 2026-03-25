"""
Schémas de requête pour le module uploads.

Contrat API entrée (Form + query). Comportement identique à api/routers/uploads.py.
"""
from typing import Literal

from pydantic import BaseModel, Field


# Valeurs autorisées pour entity_type (message 400 si autre : "entity_type doit être 'company' ou 'group'")
EntityTypeLiteral = Literal["company", "group"]


class UploadLogoForm(BaseModel):
    """Paramètres Form pour POST /logo (entity_type, entity_id)."""

    entity_type: EntityTypeLiteral = Field(
        ...,
        description="'company' ou 'group'",
    )
    entity_id: str = Field(..., description="ID de l'entité")


class LogoScaleUpdate(BaseModel):
    """Paramètre query pour PATCH /logo-scale (scale). Plage 0.5–2.0 comme en legacy."""

    scale: float = Field(
        ...,
        ge=0.5,
        le=2.0,
        description="Facteur de zoom du logo (0.5 à 2.0). Message 400 si hors plage.",
    )
