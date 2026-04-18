"""Réponses API obligations légales."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


ProfessionalInterviewStatus = Literal["up_to_date", "due_soon", "overdue", "unknown"]
SixYearReviewStatus = Literal["validated", "in_progress", "not_validated", "unknown"]


class LegalObligationStatus(BaseModel):
    employee_id: str
    employee_name: str
    hire_date: Optional[date] = None

    last_professional_interview_date: Optional[date] = None
    professional_interview_status: ProfessionalInterviewStatus
    professional_interview_next_due: Optional[date] = None

    six_year_review_status: SixYearReviewStatus
    six_year_criteria_met: bool
    six_year_next_due: Optional[date] = None
    last_six_year_review_date: Optional[date] = None

    criteria_training_completed: bool = False
    criteria_certification_obtained: bool = False
    criteria_career_evolution: bool = False


class LegalObligationOverride(BaseModel):
    employee_id: str
    criteria_training_completed: bool
    criteria_certification_obtained: bool
    criteria_career_evolution: bool
    notes: Optional[str] = None


class OverdueCountResponse(BaseModel):
    count: int = Field(ge=0)
