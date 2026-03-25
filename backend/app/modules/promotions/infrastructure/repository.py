"""
Repository promotions : persistance Supabase.

Implémentation de IPromotionRepository (lecture + écriture).
Utilise les mappers pour row → PromotionRead / PromotionListItem.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.promotions.domain.enums import PromotionStatus, PromotionType
from app.modules.promotions.domain.interfaces import IPromotionRepository
from app.modules.promotions.infrastructure.mappers import (
    row_to_promotion_list_item,
    row_to_promotion_read,
)
from app.modules.promotions.schemas import PromotionListItem, PromotionRead


class PromotionRepository(IPromotionRepository):
    """Implémentation Supabase du port IPromotionRepository."""

    def get_by_id(self, promotion_id: str, company_id: str) -> Optional[PromotionRead]:
        try:
            response = (
                supabase.table("promotions")
                .select("*")
                .eq("id", promotion_id)
                .eq("company_id", company_id)
                .single()
                .execute()
            )
            if not response.data:
                return None
            return row_to_promotion_read(response.data)
        except Exception as e:
            err = str(e).lower()
            if "pgrst116" in err or "0 rows" in err or "no rows" in err:
                return None
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la récupération de la promotion: {str(e)}",
            )

    def list(
        self,
        company_id: str,
        *,
        year: Optional[int] = None,
        status: Optional[PromotionStatus] = None,
        promotion_type: Optional[PromotionType] = None,
        employee_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[PromotionListItem]:
        try:
            query = (
                supabase.table("promotions")
                .select(
                    """
                id,
                employee_id,
                promotion_type,
                new_job_title,
                new_salary,
                new_statut,
                effective_date,
                status,
                request_date,
                grant_rh_access,
                new_rh_access,
                performance_review_id,
                created_at,
                employees!inner(
                    id,
                    first_name,
                    last_name
                ),
                requested_by_profile:profiles!promotions_requested_by_fkey(
                    id,
                    first_name,
                    last_name
                ),
                approved_by_profile:profiles!promotions_approved_by_fkey(
                    id,
                    first_name,
                    last_name
                )
                """
                )
                .eq("company_id", company_id)
            )
            if year:
                query = query.gte("effective_date", f"{year}-01-01")
                query = query.lte("effective_date", f"{year}-12-31")
            if status:
                query = query.eq("status", status)
            if promotion_type:
                query = query.eq("promotion_type", promotion_type)
            if employee_id:
                query = query.eq("employee_id", employee_id)
            query = query.order("effective_date", desc=True)
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
            response = query.execute()
            promotions = response.data or []
            if search:
                search_term = search.lower()
                filtered = []
                for promo in promotions:
                    employee = promo.get("employees", {})
                    first_name = employee.get("first_name", "").lower()
                    last_name = employee.get("last_name", "").lower()
                    job_title = (promo.get("new_job_title") or "").lower()
                    if (
                        search_term in first_name
                        or search_term in last_name
                        or search_term in job_title
                    ):
                        filtered.append(promo)
                promotions = filtered
            return [
                row_to_promotion_list_item(
                    promo,
                    promo.get("employees", {}),
                    promo.get("requested_by_profile"),
                    promo.get("approved_by_profile"),
                )
                for promo in promotions
            ]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la récupération des promotions: {str(e)}",
            )

    def create(
        self,
        data: Dict[str, Any],
        company_id: str,
        requested_by: str,
    ) -> str:
        try:
            response = supabase.table("promotions").insert(data).execute()
            if not response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Échec de la création de la promotion",
                )
            return response.data[0]["id"]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la création de la promotion: {str(e)}",
            )

    def update(
        self,
        promotion_id: str,
        company_id: str,
        data: Dict[str, Any],
    ) -> None:
        try:
            response = (
                supabase.table("promotions")
                .update(data)
                .eq("id", promotion_id)
                .eq("company_id", company_id)
                .execute()
            )
            if not response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Échec de la mise à jour de la promotion",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la mise à jour de la promotion: {str(e)}",
            )

    def delete(self, promotion_id: str, company_id: str) -> None:
        try:
            response = (
                supabase.table("promotions")
                .delete()
                .eq("id", promotion_id)
                .eq("company_id", company_id)
                .execute()
            )
            if not response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Échec de la suppression de la promotion",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la suppression de la promotion: {str(e)}",
            )


def get_promotion_repository() -> IPromotionRepository:
    """Factory : retourne le repository (implémentation Supabase)."""
    return PromotionRepository()
