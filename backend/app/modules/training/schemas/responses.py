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
    requested_by: Optional[str] = None
    manager_id: Optional[str] = None
    manager_approved_at: Optional[datetime] = None
    manager_rejected_at: Optional[datetime] = None
    manager_rejection_reason: Optional[str] = None
    rh_approved_at: Optional[datetime] = None
    rh_rejected_at: Optional[datetime] = None
    rh_rejection_reason: Optional[str] = None
    manager_display_name: Optional[str] = None
    rating: Optional[int] = None
    evaluation_comment: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    certificate_url: Optional[str] = None
    certificate_uploaded_at: Optional[datetime] = None


class CertificateUploadResponse(BaseModel):
    certificate_url: str


class TrainingEvaluationSummaryItem(BaseModel):
    training_id: str
    training_title: str
    nb_evaluations: int
    avg_rating: float
    ratings_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Nombre d'avis par note 1 à 5 (clés '1'..'5').",
    )


class TotalConsumedResponse(BaseModel):
    year: int
    total_ht: float = Field(ge=0)


class CcTrainingSuggestion(BaseModel):
    id: str
    idcc: str
    agreement_name: Optional[str] = None
    title: str
    obligation_level: str
    pedagogical_objective: Optional[str] = None
    legal_reference: Optional[str] = None
    target_roles: List[str] = Field(default_factory=list)
    periodicity: Optional[str] = None
    already_in_catalog: bool = False
    catalog_training_id: Optional[str] = None
