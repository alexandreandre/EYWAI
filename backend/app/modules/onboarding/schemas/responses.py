"""Schémas de réponse API — module onboarding."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OnboardingTaskOut(BaseModel):
    id: str
    checklist_id: str
    title: str
    description: Optional[str] = None
    category: str
    is_completed: bool
    completed_at: Optional[datetime] = None
    due_days: Optional[int] = None
    position: int


class OnboardingChecklistOut(BaseModel):
    id: str
    employee_id: str
    company_id: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    tasks: List[OnboardingTaskOut]
    nb_total: int
    nb_completed: int
    progress_pct: float


class OnboardingHubItemOut(BaseModel):
    """Résumé onboarding pour le tableau de bord RH."""

    employee_id: str
    first_name: str
    last_name: str
    job_title: Optional[str] = None
    hire_date: Optional[date] = None
    days_since_hire: Optional[int] = None
    checklist_id: Optional[str] = None
    has_checklist: bool = False
    progress_pct: float = 0.0
    nb_total: int = 0
    nb_completed: int = 0
    nb_overdue: int = 0
    completed_at: Optional[datetime] = None
    checklist_created_at: Optional[datetime] = None


class OnboardingHubKpisOut(BaseModel):
    in_progress: int = 0
    overdue_tasks: int = 0
    completed_this_month: int = 0


class OnboardingHubListOut(BaseModel):
    items: List[OnboardingHubItemOut] = Field(default_factory=list)
    kpis: OnboardingHubKpisOut = Field(default_factory=OnboardingHubKpisOut)
    lookback_days: int = 90
