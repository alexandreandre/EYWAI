"""
Schémas de requête pour le module annual_reviews.

Source de vérité pour les schémas annual_reviews. L'ancien fichier
schemas/annual_review.py réexporte depuis ici pour compatibilité.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.modules.annual_reviews.domain.interview_types import InterviewType

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


class InterviewCampaignSettingsUpdate(BaseModel):
    """Politique d'entretien d'une société (company_interview_settings).

    Les contraintes reprennent celles de la base : un mois est obligatoire en mois
    fixe, interdit sur l'anniversaire d'embauche.
    """

    enabled: bool = False
    campaign_mode: Literal["mois_fixe", "anniversaire_embauche"] = "mois_fixe"
    campaign_month: Optional[int] = Field(default=None, ge=1, le=12)
    periodicity_years: int = Field(default=1, ge=1, le=6)

    @model_validator(mode="after")
    def _mois_coherent(self) -> "InterviewCampaignSettingsUpdate":
        if self.campaign_mode == "mois_fixe" and self.campaign_month is None:
            raise ValueError("Un mois de campagne est obligatoire en mode mois fixe.")
        if self.campaign_mode == "anniversaire_embauche":
            self.campaign_month = None
        return self
