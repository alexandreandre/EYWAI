"""
Schémas de requête pour le module annual_reviews.

Source de vérité pour les schémas annual_reviews. L'ancien fichier
schemas/annual_review.py réexporte depuis ici pour compatibilité.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

InterviewType = Literal[
    "annual_performance",
    "professional_2ans",
    "competency_6ans",
    "return_absence",
    "mid_year",
    "other",
]

AnnualReviewStatus = Literal[
    "planifie",  # RH a planifié avec notes
    "en_attente_acceptation",  # En attente de l'acceptation de l'employé
    "accepte",  # Employé a accepté
    "refuse",  # Employé a refusé
    "realise",  # Entretien réalisé
    "cloture",  # Entretien clôturé avec compte-rendu
]


class AnnualReviewBase(BaseModel):
    """Schéma de base pour un entretien annuel."""

    year: int = Field(..., ge=2000, le=2100)
    status: AnnualReviewStatus = "planifie"
    planned_date: Optional[date] = None
    completed_date: Optional[date] = None
    employee_preparation_notes: Optional[str] = None
    rh_preparation_template: Optional[str] = None  # Notes RH pour l'entretien
    employee_acceptance_status: Optional[Literal["accepte", "refuse"]] = None
    employee_acceptance_date: Optional[datetime] = None
    meeting_report: Optional[str] = None  # Compte-rendu d'entretien


class AnnualReviewCreate(BaseModel):
    """Schéma pour la création d'un entretien annuel."""

    employee_id: str
    year: int = Field(..., ge=2000, le=2100)
    status: AnnualReviewStatus = "en_attente_acceptation"
    planned_date: Optional[date] = None
    rh_preparation_template: Optional[str] = None  # Notes RH pour l'entretien
    interview_type: InterviewType = "annual_performance"
    template_id: Optional[str] = None


class AnnualReviewUpdate(BaseModel):
    """Schéma pour la mise à jour partielle d'un entretien annuel."""

    planned_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[AnnualReviewStatus] = None
    employee_preparation_notes: Optional[str] = None
    rh_preparation_template: Optional[str] = None
    employee_acceptance_status: Optional[Literal["accepte", "refuse"]] = None
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
    interview_type: Optional[InterviewType] = None
    template_id: Optional[str] = None


class SendForSignatureBody(BaseModel):
    """Corps optionnel pour l'envoi en signature Yousign."""

    second_signer_email: Optional[str] = None
    expiration_days: int = Field(default=15, ge=1, le=365)
