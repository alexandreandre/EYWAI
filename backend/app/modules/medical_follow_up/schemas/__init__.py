# app/modules/medical_follow_up/schemas/__init__.py
"""Schémas du module medical_follow_up (définitions canoniques)."""

from app.modules.medical_follow_up.schemas.requests import (
    CreateOnDemandBody,
    MarkCompletedBody,
    MarkPlanifiedBody,
)
from app.modules.medical_follow_up.schemas.responses import (
    KPIsResponse,
    ObligationListItem,
    SettingsResponse,
)

__all__ = [
    "CreateOnDemandBody",
    "KPIsResponse",
    "MarkCompletedBody",
    "MarkPlanifiedBody",
    "ObligationListItem",
    "SettingsResponse",
]
