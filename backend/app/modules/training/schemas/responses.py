"""Schémas de réponse catalogue formations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrainingCatalog(BaseModel):
    id: str
    company_id: str
    title: str
    training_type: str
    provider: Optional[str] = None
    duration_hours: Optional[float] = None
    unit_cost_ht: Optional[float] = None
    pedagogical_objective: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    certification_id: Optional[str] = None
    competency_id: Optional[str] = None
    status: str
    program_url: Optional[str] = None
    external_link: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    certification_ref: Optional[Dict[str, Any]] = None
    enrolled_count: int = 0


class TrainingEnrollment(BaseModel):
    id: str
    company_id: str
    training_id: str
    employee_id: str
    status: str
    planned_date: Optional[date] = None
    completion_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    employee_name: Optional[str] = None
    training_title: Optional[str] = None
    unit_cost_ht: Optional[float] = None
    suggest_certification_creation: bool = False
    suggested_certification_id: Optional[str] = None


class TotalConsumedResponse(BaseModel):
    year: int
    total_ht: float = Field(ge=0)
