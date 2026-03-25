"""
Mappers entre lignes Supabase et schémas du module promotions.

Conversions row → PromotionRead, row (+ joins) → PromotionListItem.
Aucune logique métier, uniquement transformation de données.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.promotions.schemas import PromotionListItem, PromotionRead


def parse_date(value: Any) -> date:
    if value is None:
        raise ValueError("date attendue")
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def row_to_promotion_read(promo: Dict[str, Any]) -> PromotionRead:
    """Convertit une ligne table promotions en PromotionRead."""
    return PromotionRead(
        id=promo["id"],
        company_id=promo["company_id"],
        employee_id=promo["employee_id"],
        promotion_type=promo["promotion_type"],
        previous_job_title=promo.get("previous_job_title"),
        previous_salary=promo.get("previous_salary"),
        previous_statut=promo.get("previous_statut"),
        previous_classification=promo.get("previous_classification"),
        new_job_title=promo.get("new_job_title"),
        new_salary=promo.get("new_salary"),
        new_statut=promo.get("new_statut"),
        new_classification=promo.get("new_classification"),
        previous_rh_access=promo.get("previous_rh_access"),
        new_rh_access=promo.get("new_rh_access"),
        grant_rh_access=promo.get("grant_rh_access", False),
        effective_date=parse_date(promo["effective_date"]),
        request_date=parse_date(promo["request_date"]),
        status=promo["status"],
        reason=promo.get("reason"),
        justification=promo.get("justification"),
        performance_review_id=promo.get("performance_review_id"),
        requested_by=promo.get("requested_by"),
        approved_by=promo.get("approved_by"),
        approved_at=parse_datetime(promo.get("approved_at")),
        rejection_reason=promo.get("rejection_reason"),
        notes=promo.get("notes"),
        promotion_letter_url=promo.get("promotion_letter_url"),
        created_at=parse_datetime(promo["created_at"]) or datetime.now(),
        updated_at=parse_datetime(promo["updated_at"]) or datetime.now(),
    )


def row_to_promotion_list_item(
    promo: Dict[str, Any],
    employee: Dict[str, Any],
    requested_by_profile: Optional[Dict[str, Any]],
    approved_by_profile: Optional[Dict[str, Any]],
) -> PromotionListItem:
    """Convertit une ligne promotions + joins en PromotionListItem."""
    requested_by_name = None
    if requested_by_profile:
        first = requested_by_profile.get("first_name", "")
        last = requested_by_profile.get("last_name", "")
        requested_by_name = f"{first} {last}".strip() if first or last else None
    approved_by_name = None
    if approved_by_profile:
        first = approved_by_profile.get("first_name", "")
        last = approved_by_profile.get("last_name", "")
        approved_by_name = f"{first} {last}".strip() if first or last else None
    return PromotionListItem(
        id=promo["id"],
        employee_id=promo["employee_id"],
        first_name=employee.get("first_name", ""),
        last_name=employee.get("last_name", ""),
        promotion_type=promo["promotion_type"],
        new_job_title=promo.get("new_job_title"),
        new_salary=promo.get("new_salary"),
        new_statut=promo.get("new_statut"),
        effective_date=parse_date(promo["effective_date"]),
        status=promo["status"],
        request_date=parse_date(promo["request_date"]),
        requested_by_name=requested_by_name,
        approved_by_name=approved_by_name,
        grant_rh_access=promo.get("grant_rh_access", False),
        new_rh_access=promo.get("new_rh_access"),
        performance_review_id=promo.get("performance_review_id"),
        created_at=parse_datetime(promo["created_at"]) or datetime.now(),
    )


__all__ = [
    "parse_date",
    "parse_datetime",
    "row_to_promotion_read",
    "row_to_promotion_list_item",
]
