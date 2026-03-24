# Domain layer for bonus_types.
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.domain.interfaces import (
    IBonusTypeRepository,
    IEmployeeHoursProvider,
)
from app.modules.bonus_types.domain.rules import (
    compute_bonus_amount,
    validate_seuil_heures_for_kind,
)
from app.modules.bonus_types.domain.value_objects import BonusAmountComputation

__all__ = [
    "BonusType",
    "BonusTypeKind",
    "BonusAmountComputation",
    "IBonusTypeRepository",
    "IEmployeeHoursProvider",
    "compute_bonus_amount",
    "validate_seuil_heures_for_kind",
]
