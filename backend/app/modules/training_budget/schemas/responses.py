"""Schémas de réponse API budget formation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class TrainingBudget(BaseModel):
    id: str
    company_id: str
    year: int
    global_envelope: float
    alert_threshold_1: float = Field(default=70.0)
    alert_threshold_2: float = Field(default=90.0)
    service_breakdown: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TrainingBudgetWithConsumption(TrainingBudget):
    consumed: float
    remaining: float
    consumption_pct: float
    alert_level: Literal["none", "warning", "critical"]


__all__ = ["TrainingBudget", "TrainingBudgetWithConsumption"]
