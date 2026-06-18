"""
Enums du domaine mutuelle_types.
"""

from __future__ import annotations

from enum import Enum


class PackCouverture(str, Enum):
    """Type de couverture complémentaire santé."""

    ISOLE = "isole"
    FAMILLE = "famille"
    DUO = "duo"
    AUTRE = "autre"


class StatutCategorielMutuelle(str, Enum):
    """Catégorie salariale visée par une formule mutuelle."""

    CADRE = "cadre"
    NON_CADRE = "non_cadre"
    TOUS = "tous"
