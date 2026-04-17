"""Schémas objectifs."""

from app.modules.objectives.schemas.requests import (
    CheckinCreate,
    CompanyServiceCreate,
    MilestoneCreate,
    MilestoneUpdate,
    ObjectiveCreate,
    ObjectiveEvaluate,
    ObjectiveUpdate,
)
from app.modules.objectives.schemas.responses import (
    AchievementRateResponse,
    CompanyService,
    DeclineToTeamResult,
    EmployeeObjective,
    ObjectiveCheckin,
    ObjectiveMilestone,
)

__all__ = [
    "AchievementRateResponse",
    "CheckinCreate",
    "CompanyServiceCreate",
    "CompanyService",
    "DeclineToTeamResult",
    "EmployeeObjective",
    "MilestoneCreate",
    "MilestoneUpdate",
    "ObjectiveCheckin",
    "ObjectiveCreate",
    "ObjectiveEvaluate",
    "ObjectiveMilestone",
    "ObjectiveUpdate",
]
