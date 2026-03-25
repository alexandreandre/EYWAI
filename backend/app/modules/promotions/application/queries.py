"""
Queries (cas d'usage lecture) du module promotions.

Délègue au repository et à IPromotionQueries. Aucune logique DB directe.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException

from app.modules.promotions.infrastructure.queries import get_promotion_queries
from app.modules.promotions.infrastructure.repository import get_promotion_repository
from app.modules.promotions.schemas import (
    EmployeeRhAccess,
    PromotionListItem,
    PromotionRead,
    PromotionStats,
)


def list_promotions_query(
    company_id: str,
    year: Optional[int] = None,
    status: Optional[str] = None,
    promotion_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[PromotionListItem]:
    """Liste les promotions avec filtres (délègue au repository)."""
    return get_promotion_repository().list(
        company_id=company_id,
        year=year,
        status=status,
        promotion_type=promotion_type,
        employee_id=employee_id,
        search=search,
        limit=limit,
        offset=offset,
    )


def get_promotion_by_id_query(promotion_id: str, company_id: str) -> PromotionRead:
    """Détail d'une promotion (délègue au repository, 404 si absente)."""
    promotion = get_promotion_repository().get_by_id(promotion_id, company_id)
    if promotion is None:
        raise HTTPException(status_code=404, detail="Promotion non trouvée")
    return promotion


def get_promotion_stats_query(
    company_id: str,
    year: Optional[int] = None,
) -> PromotionStats:
    """Statistiques des promotions (délègue à IPromotionQueries)."""
    return get_promotion_queries().get_promotion_stats(
        company_id=company_id,
        year=year,
    )


def get_employee_rh_access_query(
    employee_id: str,
    company_id: str,
) -> EmployeeRhAccess:
    """Accès RH actuel d'un employé (délègue à IPromotionQueries)."""
    return get_promotion_queries().get_employee_rh_access(
        employee_id=employee_id,
        company_id=company_id,
    )


def get_promotion_document_stream_query(promotion_id: str, company_id: str):
    """Stream du PDF de promotion (délègue au provider)."""
    from app.modules.promotions.infrastructure.providers import (
        get_promotion_document_provider,
    )

    return get_promotion_document_provider().get_pdf_stream(
        promotion_id=promotion_id,
        company_id=company_id,
    )


__all__ = [
    "list_promotions_query",
    "get_promotion_by_id_query",
    "get_promotion_stats_query",
    "get_employee_rh_access_query",
    "get_promotion_document_stream_query",
]
