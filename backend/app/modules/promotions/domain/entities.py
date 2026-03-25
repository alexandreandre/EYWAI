"""
Entités du domaine promotions.

Placeholder : structure minimale pour la migration.
À terme : entité Promotion riche avec invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.modules.promotions.domain.enums import (
    PromotionStatus,
    PromotionType,
    RhAccessRole,
)


@dataclass
class Promotion:
    """
    Agrégat promotion (placeholder).
    Les champs reflètent la table promotions + relations.
    """

    id: str
    company_id: str
    employee_id: str
    promotion_type: PromotionType
    status: PromotionStatus
    effective_date: date
    request_date: date
    # Snapshot avant
    previous_job_title: Optional[str] = None
    previous_salary: Optional[Dict[str, Any]] = None
    previous_statut: Optional[str] = None
    previous_classification: Optional[Dict[str, Any]] = None
    previous_rh_access: Optional[str] = None
    # Snapshot après
    new_job_title: Optional[str] = None
    new_salary: Optional[Dict[str, Any]] = None
    new_statut: Optional[str] = None
    new_classification: Optional[Dict[str, Any]] = None
    new_rh_access: Optional[RhAccessRole] = None
    grant_rh_access: bool = False
    reason: Optional[str] = None
    justification: Optional[str] = None
    performance_review_id: Optional[str] = None
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[List[Dict[str, Any]]] = None
    promotion_letter_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = ["Promotion"]
