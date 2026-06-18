# Schemas for repos_compensateur.

from app.modules.repos_compensateur.schemas.requests import (
    ContingentSettingsUpdate,
    EmployeeAdjustmentUpdate,
)
from app.modules.repos_compensateur.schemas.responses import (
    CalculerCreditsResponse,
    ContingentEmployeeDetailResponse,
    ContingentOverviewResponse,
    ContingentSettingsResponse,
    EmployeeAdjustmentResponse,
)

__all__ = [
    "CalculerCreditsResponse",
    "ContingentEmployeeDetailResponse",
    "ContingentOverviewResponse",
    "ContingentSettingsResponse",
    "ContingentSettingsUpdate",
    "EmployeeAdjustmentResponse",
    "EmployeeAdjustmentUpdate",
]
