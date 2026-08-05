"""Entrées d'API des périodes d'essai."""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TrialUnit = Literal["jours", "semaines", "mois"]


class TrialPeriodCreate(BaseModel):
    employee_id: str
    start_date: date
    duration_value: int = Field(gt=0)
    duration_unit: TrialUnit = "mois"
    renewal_allowed: bool = False


class TrialPeriodUpdate(BaseModel):
    start_date: Optional[date] = None
    duration_value: Optional[int] = Field(default=None, gt=0)
    duration_unit: Optional[TrialUnit] = None
    renewal_allowed: Optional[bool] = None


class TrialPeriodRenew(BaseModel):
    renewed_at: date
    duration_value: int = Field(gt=0)
    duration_unit: TrialUnit


class TrialPeriodApplyBareme(BaseModel):
    employee_ids: List[str] = Field(min_length=1)
