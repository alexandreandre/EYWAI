# Schemas for bonus_types.
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.schemas.requests import BonusTypeCreate, BonusTypeUpdate
from app.modules.bonus_types.schemas.responses import (
    BonusCalculationResultResponse,
    BonusType,
)

# Alias pour compatibilité avec l’ancien nom BonusTypeEnum (même enum, même valeurs).
BonusTypeEnum = BonusTypeKind

__all__ = [
    "BonusType",
    "BonusTypeCreate",
    "BonusTypeUpdate",
    "BonusTypeEnum",
    "BonusTypeKind",
    "BonusCalculationResultResponse",
]
