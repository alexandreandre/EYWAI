"""Queries : suggestions d'entretiens annuels à planifier."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.annual_reviews.domain.campaign import InterviewCampaignSettings
from app.modules.annual_reviews.domain.planning_suggestions import (
    PlanningSuggestion,
    compute_planning_suggestions,
)
from app.modules.annual_reviews.infrastructure import queries as infra_queries


def get_campaign_settings(company_id: str) -> InterviewCampaignSettings:
    """Politique d'entretien de la société, ou le défaut inerte si jamais réglée."""
    return InterviewCampaignSettings.from_row(
        infra_queries.query_interview_settings(company_id)
    )


def save_campaign_settings(
    company_id: str, values: Dict[str, Any]
) -> InterviewCampaignSettings:
    """Enregistre la politique d'entretien de la société."""
    return InterviewCampaignSettings.from_row(
        infra_queries.upsert_interview_settings(company_id, values)
    )


def list_planning_suggestions(
    company_id: str,
    year: Optional[int] = None,
) -> List[PlanningSuggestion]:
    """Entretiens à planifier pour l'année demandée.

    Sans réglage de campagne, seuls les cadres et forfaits jour ressortent. Réglage
    posé, la campagne de la société couvre l'ensemble de son effectif actif.
    """
    target_year = year if year is not None else date.today().year
    settings = get_campaign_settings(company_id)
    employees = infra_queries.query_list_active_employees(company_id)
    reviews: List[Dict[str, Any]] = (
        infra_queries.query_reviews_for_company(company_id)
        if settings.enabled
        else infra_queries.query_reviews_for_company_year(company_id, target_year)
    )
    return compute_planning_suggestions(
        employees, reviews, target_year, settings=settings
    )
