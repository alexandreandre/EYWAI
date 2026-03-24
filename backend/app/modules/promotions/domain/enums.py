"""
Types et énumérations du domaine promotions.

Alignés sur schemas.promotion (legacy). À terme : source de vérité du domain.
"""
from __future__ import annotations

from typing import Literal

# Statuts du workflow de promotion
PromotionStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "effective",
    "cancelled",
]

# Type de promotion (poste, salaire, statut, classification, mixte)
PromotionType = Literal[
    "poste",
    "salaire",
    "statut",
    "classification",
    "mixte",
]

# Rôles d'accès RH
RhAccessRole = Literal[
    "collaborateur_rh",
    "rh",
    "admin",
]

__all__ = ["PromotionStatus", "PromotionType", "RhAccessRole"]
