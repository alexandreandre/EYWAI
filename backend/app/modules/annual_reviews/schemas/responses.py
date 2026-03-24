"""
Schémas de réponse pour le module annual_reviews.

Source de vérité pour Read/ListItem. L'ancien fichier schemas/annual_review.py
réexporte depuis ici pour compatibilité.
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

from .requests import AnnualReviewStatus


class AnnualReviewRead(BaseModel):
    """Schéma pour la lecture d'un entretien annuel."""

    id: str
    employee_id: str
    company_id: str
    year: int
    status: AnnualReviewStatus
    planned_date: Optional[date] = None
    completed_date: Optional[date] = None
    employee_preparation_notes: Optional[str] = None
    employee_preparation_validated_at: Optional[datetime] = None
    rh_preparation_template: Optional[str] = None
    employee_acceptance_status: Optional[Literal["accepte", "refuse"]] = None
    employee_acceptance_date: Optional[datetime] = None
    meeting_report: Optional[str] = None  # Compte-rendu d'entretien
    # Champs RH pour la fiche complète
    rh_notes: Optional[str] = None
    evaluation_summary: Optional[str] = None
    objectives_achieved: Optional[str] = None
    objectives_next_year: Optional[str] = None
    strengths: Optional[str] = None
    improvement_areas: Optional[str] = None
    training_needs: Optional[str] = None
    career_development: Optional[str] = None
    salary_review: Optional[str] = None
    overall_rating: Optional[str] = None
    next_review_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnnualReviewListItem(BaseModel):
    """Schéma pour un item de la liste consolidée RH."""

    id: str
    employee_id: str
    first_name: str
    last_name: str
    job_title: Optional[str] = None
    year: int
    status: AnnualReviewStatus
    planned_date: Optional[date] = None
    completed_date: Optional[date] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
