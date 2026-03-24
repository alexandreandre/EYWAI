"""
Schémas Pydantic de base partagés.

Config commune (alias, validation) ; pas de champs métier.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SharedBaseModel(BaseModel):
    """Base pour les schémas partagés : config commune."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
        extra="forbid",
    )
