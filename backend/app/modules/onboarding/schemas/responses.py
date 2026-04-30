"""Schémas de réponse API — module onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


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
