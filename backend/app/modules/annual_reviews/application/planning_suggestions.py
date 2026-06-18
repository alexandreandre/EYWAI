"""Queries : suggestions d'entretiens annuels à planifier."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.modules.annual_reviews.domain.planning_suggestions import (
    PlanningSuggestion,
    compute_planning_suggestions,
)
from app.modules.annual_reviews.infrastructure import queries as infra_queries


def list_planning_suggestions(
    company_id: str,
    year: Optional[int] = None,
) -> List[PlanningSuggestion]:
    """Salariés cadres / forfait jour sans entretien annuel couvert pour l'année."""
    target_year = year if year is not None else date.today().year
    employees = infra_queries.query_list_active_employees(company_id)
    reviews = infra_queries.query_reviews_for_company_year(company_id, target_year)
    return compute_planning_suggestions(employees, reviews, target_year)
