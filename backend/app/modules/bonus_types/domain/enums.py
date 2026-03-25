"""
Types de primes (catalogue entreprise).

Aligné sur le legacy : schemas.bonus_type.BonusTypeEnum.
"""

from enum import Enum


class BonusTypeKind(str, Enum):
    """Types de primes disponibles."""

    MONTANT_FIXE = "montant_fixe"
    SELON_HEURES = "selon_heures"
