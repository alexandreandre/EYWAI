# Domain layer for participation.
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.domain.enums import DistributionMode
from app.modules.participation.domain.rules import (
    compute_presence_days_for_schedules,
    compute_seniority_years,
    extract_annual_salary_from_cumuls,
)

__all__ = [
    "ParticipationSimulation",
    "DistributionMode",
    "compute_presence_days_for_schedules",
    "compute_seniority_years",
    "extract_annual_salary_from_cumuls",
]
