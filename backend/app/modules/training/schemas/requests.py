"""Schémas de requête catalogue formations."""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

TrainingType = Literal["presentiel", "distanciel", "elearning", "blended", "habilitation"]
EnrollmentStatus = Literal["planned", "in_progress", "completed", "cancelled"]

_TRAINING_TYPES = frozenset(
    {"presentiel", "distanciel", "elearning", "blended", "habilitation"}
)
_ENROLLMENT_STATUSES = frozenset({"planned", "in_progress", "completed", "cancelled"})


class TrainingCatalogCreate(BaseModel):
    title: str
    training_type: TrainingType
    provider: Optional[str] = None
    duration_hours: Optional[float] = None
    unit_cost_ht: Optional[float] = None
    pedagogical_objective: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    certification_id: Optional[str] = None
    competency_id: Optional[str] = None
    program_url: Optional[str] = None
    external_link: Optional[str] = None

    @field_validator("training_type", mode="before")
    @classmethod
    def validate_training_type(cls, v: object) -> object:
        if v is None:
            return v
        s = str(v).strip().lower()
        if s not in _TRAINING_TYPES:
            raise ValueError(
                "training_type doit être presentiel, distanciel, elearning, blended ou habilitation."
            )
        return s


class TrainingCatalogUpdate(BaseModel):
    title: Optional[str] = None
    training_type: Optional[TrainingType] = None
    provider: Optional[str] = None
    duration_hours: Optional[float] = None
    unit_cost_ht: Optional[float] = None
    pedagogical_objective: Optional[str] = None
    categories: Optional[List[str]] = None
    certification_id: Optional[str] = None
    competency_id: Optional[str] = None
    program_url: Optional[str] = None
    external_link: Optional[str] = None
    status: Optional[str] = None

    @field_validator("training_type", mode="before")
    @classmethod
    def validate_training_type(cls, v: object) -> object:
        if v is None or v == "":
            return v
        s = str(v).strip().lower()
        if s not in _TRAINING_TYPES:
            raise ValueError(
                "training_type doit être presentiel, distanciel, elearning, blended ou habilitation."
            )
        return s


class TrainingEnrollmentCreate(BaseModel):
    training_id: str
    employee_id: str
    status: EnrollmentStatus = "planned"
    planned_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: object) -> object:
        if v is None:
            return v
        s = str(v).strip().lower()
        if s not in _ENROLLMENT_STATUSES:
            raise ValueError(
                "status doit être planned, in_progress, completed ou cancelled."
            )
        return s


class TrainingEnrollmentUpdate(BaseModel):
    status: Optional[EnrollmentStatus] = None
    planned_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: object) -> object:
        if v is None or v == "":
            return v
        s = str(v).strip().lower()
        if s not in _ENROLLMENT_STATUSES:
            raise ValueError(
                "status doit être planned, in_progress, completed ou cancelled."
            )
        return s
