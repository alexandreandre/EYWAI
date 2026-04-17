"""Schémas de réponse objectifs & KPI."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ObjectiveMilestone(BaseModel):
    id: str
    objective_id: str
    milestone_date: date
    expected_value: float
    actual_value: Optional[float] = None
    comment: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class ObjectiveCheckin(BaseModel):
    id: str
    objective_id: str
    checkin_date: date
    progress_note: str
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class EmployeeObjective(BaseModel):
    id: str
    company_id: str
    employee_id: Optional[str] = None
    service_id: Optional[str] = None
    parent_objective_id: Optional[str] = None
    title: str
    type: str
    period_year: int
    status: str
    description: Optional[str] = None
    kpi_label: Optional[str] = None
    kpi_unit: Optional[str] = None
    kpi_target_value: Optional[float] = None
    kpi_initial_value: Optional[float] = None
    due_date: Optional[date] = None
    weight: Optional[float] = None
    annual_review_id: Optional[str] = None
    notes: Optional[str] = None
    evaluation_date: Optional[date] = None
    final_achievement_rate: Optional[float] = None
    evaluation_comment: Optional[str] = None
    evaluated_in_review_id: Optional[str] = None
    last_modified_by: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    milestones: List[ObjectiveMilestone] = Field(default_factory=list)
    checkins: List[ObjectiveCheckin] = Field(default_factory=list)
    employee_name: Optional[str] = None
    service_name: Optional[str] = None


class CompanyService(BaseModel):
    id: str
    company_id: str
    name: str
    created_at: Optional[datetime] = None


class DeclineToTeamResult(BaseModel):
    created_count: int = Field(ge=0)


class AchievementRateResponse(BaseModel):
    rate: Optional[float] = Field(None, description="Moyenne pondérée (%) ou null si aucune donnée.")
