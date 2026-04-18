"""Schémas de requête objectifs & KPI."""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CompanyServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

ObjectiveType = Literal["quantitative", "qualitative"]
ObjectiveStatus = Literal[
    "draft",
    "active",
    "achieved",
    "partially_achieved",
    "not_achieved",
    "cancelled",
]


class MilestoneCreate(BaseModel):
    milestone_date: date
    expected_value: float
    comment: Optional[str] = None


class MilestoneUpdate(BaseModel):
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    comment: Optional[str] = None


class CheckinCreate(BaseModel):
    checkin_date: date
    progress_note: str


class ObjectiveCreate(BaseModel):
    employee_id: Optional[str] = None
    service_id: Optional[str] = None
    title: str
    type: ObjectiveType
    period_year: int
    status: ObjectiveStatus = "active"
    description: Optional[str] = None
    kpi_label: Optional[str] = None
    kpi_unit: Optional[str] = None
    kpi_target_value: Optional[float] = None
    kpi_initial_value: Optional[float] = None
    due_date: Optional[date] = None
    weight: Optional[float] = None
    annual_review_id: Optional[str] = None
    notes: Optional[str] = None
    milestones: List[MilestoneCreate] = Field(default_factory=list)

    @field_validator("kpi_target_value")
    @classmethod
    def kpi_target_not_zero(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v == 0:
            raise ValueError("kpi_target_value ne peut pas être 0.")
        return v

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("La pondération doit être comprise entre 0 et 100.")
        return v

    @model_validator(mode="after")
    def validate_scope_and_type(self) -> "ObjectiveCreate":
        if self.employee_id and self.service_id:
            raise ValueError("Choisissez soit un collaborateur, soit un service, pas les deux.")
        if not self.employee_id and not self.service_id:
            raise ValueError("Renseignez un collaborateur (objectif individuel) ou un service (objectif équipe).")
        if self.type == "quantitative":
            if not self.kpi_label or not str(self.kpi_label).strip():
                raise ValueError("Pour un objectif quantitatif, kpi_label est requis.")
            if self.kpi_target_value is None:
                raise ValueError("Pour un objectif quantitatif, kpi_target_value est requis.")
        if self.type == "qualitative":
            if not self.description or not str(self.description).strip():
                raise ValueError("Pour un objectif qualitatif, description est requise.")
        return self


class ObjectiveUpdate(BaseModel):
    employee_id: Optional[str] = None
    service_id: Optional[str] = None
    title: Optional[str] = None
    type: Optional[ObjectiveType] = None
    period_year: Optional[int] = None
    status: Optional[ObjectiveStatus] = None
    description: Optional[str] = None
    kpi_label: Optional[str] = None
    kpi_unit: Optional[str] = None
    kpi_target_value: Optional[float] = None
    kpi_initial_value: Optional[float] = None
    due_date: Optional[date] = None
    weight: Optional[float] = None
    annual_review_id: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("kpi_target_value")
    @classmethod
    def kpi_target_not_zero(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v == 0:
            raise ValueError("kpi_target_value ne peut pas être 0.")
        return v

    @field_validator("weight")
    @classmethod
    def weight_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError("La pondération doit être comprise entre 0 et 100.")
        return v

class ObjectiveEvaluate(BaseModel):
    final_achievement_rate: float
    status: ObjectiveStatus
    evaluation_comment: Optional[str] = None
    evaluation_date: Optional[date] = None
    evaluated_in_review_id: Optional[str] = None
