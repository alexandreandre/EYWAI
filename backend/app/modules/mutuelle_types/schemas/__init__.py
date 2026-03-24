"""
Schémas API du module mutuelle_types.

Réexport des contrats requêtes/réponses pour l’api et l’application.
"""
from __future__ import annotations

from app.modules.mutuelle_types.schemas.requests import (
    MutuelleTypeCreate,
    MutuelleTypeUpdate,
)
from app.modules.mutuelle_types.schemas.responses import MutuelleType

__all__ = [
    "MutuelleType",
    "MutuelleTypeCreate",
    "MutuelleTypeUpdate",
]
