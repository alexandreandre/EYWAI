"""Schémas de requête compétences."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CompetencyCategory = Literal[
    "technique",
    "manageriale",
    "transversale",
    "reglementaire",
    "securite",
]


class CompetencyRefCreate(BaseModel):
    name: str = Field(min_length=1)
    category: CompetencyCategory
    description: Optional[str] = None
    required_level: Optional[int] = Field(None, ge=1, le=4)


class CompetencyRefUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    category: Optional[CompetencyCategory] = None
    description: Optional[str] = None
    required_level: Optional[int] = Field(None, ge=1, le=4)
    status: Optional[str] = None


class EmployeeCompetencyCreate(BaseModel):
    employee_id: str
    competency_id: str
    score: int = Field(ge=0, le=4)
    evaluation_date: date
    comment: Optional[str] = None

    @field_validator("score")
    @classmethod
    def score_range(cls, v: int) -> int:
        if v < 0 or v > 4:
            raise ValueError("Le score doit être entre 0 et 4.")
        return v


class EmployeeCompetencyUpdate(BaseModel):
    score: Optional[int] = Field(None, ge=0, le=4)
    evaluation_date: Optional[date] = None
    comment: Optional[str] = None
