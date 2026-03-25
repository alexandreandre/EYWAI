"""
Schémas API du module promotions.

Définitions canoniques dans requests.py et responses.py.
"""

from __future__ import annotations

from app.modules.promotions.schemas.requests import (
    PromotionApprove,
    PromotionCreate,
    PromotionReject,
    PromotionUpdate,
)
from app.modules.promotions.schemas.responses import (
    EmployeeRhAccess,
    PromotionBase,
    PromotionListItem,
    PromotionRead,
    PromotionStats,
    PromotionStatus,
    PromotionType,
    RhAccessRole,
)

__all__ = [
    "PromotionCreate",
    "PromotionUpdate",
    "PromotionApprove",
    "PromotionReject",
    "PromotionRead",
    "PromotionListItem",
    "PromotionStats",
    "PromotionBase",
    "EmployeeRhAccess",
    "PromotionStatus",
    "PromotionType",
    "RhAccessRole",
]
