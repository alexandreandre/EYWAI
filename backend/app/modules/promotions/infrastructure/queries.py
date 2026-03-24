"""
Requêtes agrégées : stats promotions, accès RH employé.

Implémentation de IPromotionQueries (Supabase).
Pas de logique métier pure : délégation à domain.rules pour les rôles disponibles.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.promotions.domain.interfaces import IPromotionQueries
from app.modules.promotions.domain.rules import get_available_rh_roles
from app.modules.promotions.schemas import EmployeeRhAccess, PromotionStats


class PromotionQueries(IPromotionQueries):
    """Implémentation Supabase du port IPromotionQueries."""

    def get_promotion_stats(
        self,
        company_id: str,
        year: Optional[int] = None,
    ) -> PromotionStats:
        try:
            query = (
                supabase.table("promotions")
                .select(
                    "id, status, promotion_type, effective_date, new_salary, previous_salary, grant_rh_access"
                )
                .eq("company_id", company_id)
            )
            if year:
                query = query.gte("effective_date", f"{year}-01-01")
                query = query.lte("effective_date", f"{year}-12-31")
            response = query.execute()
            promotions = response.data or []

            total_promotions = len(promotions)
            promotions_by_month: Dict[str, int] = {}
            for promo in promotions:
                effective_date = promo.get("effective_date")
                if effective_date:
                    if isinstance(effective_date, str):
                        effective_date = date.fromisoformat(effective_date)
                    month_key = f"{effective_date.year}-{effective_date.month:02d}"
                    promotions_by_month[month_key] = (
                        promotions_by_month.get(month_key, 0) + 1
                    )

            approved_count = sum(1 for p in promotions if p.get("status") == "approved")
            rejected_count = sum(1 for p in promotions if p.get("status") == "rejected")
            total_submitted = approved_count + rejected_count
            approval_rate = (
                (approved_count / total_submitted * 100) if total_submitted > 0 else 0.0
            )

            promotions_by_type: Dict[str, int] = {}
            for promo in promotions:
                pt = promo.get("promotion_type", "unknown")
                promotions_by_type[pt] = promotions_by_type.get(pt, 0) + 1

            salary_increases: List[float] = []
            for promo in promotions:
                new_salary = promo.get("new_salary")
                previous_salary = promo.get("previous_salary")
                if new_salary and previous_salary:
                    new_value = (
                        new_salary.get("valeur")
                        if isinstance(new_salary, dict)
                        else None
                    )
                    prev_value = (
                        previous_salary.get("valeur")
                        if isinstance(previous_salary, dict)
                        else None
                    )
                    if new_value and prev_value and prev_value > 0:
                        salary_increases.append(
                            ((new_value - prev_value) / prev_value) * 100
                        )
            average_salary_increase = (
                sum(salary_increases) / len(salary_increases) if salary_increases else None
            )
            promotions_with_rh_access = sum(
                1 for p in promotions if p.get("grant_rh_access", False)
            )

            return PromotionStats(
                total_promotions=total_promotions,
                promotions_by_month=promotions_by_month,
                approval_rate=round(approval_rate, 2),
                promotions_by_type=promotions_by_type,
                average_salary_increase=(
                    round(average_salary_increase, 2)
                    if average_salary_increase is not None
                    else None
                ),
                promotions_with_rh_access=promotions_with_rh_access,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors du calcul des statistiques: {str(e)}",
            )

    def get_employee_rh_access(
        self,
        employee_id: str,
        company_id: str,
    ) -> EmployeeRhAccess:
        try:
            employee_response = (
                supabase.table("employees")
                .select("id, user_id")
                .eq("id", employee_id)
                .eq("company_id", company_id)
                .single()
                .execute()
            )
            if not employee_response.data:
                raise HTTPException(status_code=404, detail="Employé non trouvé")
            employee = employee_response.data
            user_id = employee.get("user_id")

            current_role = None
            has_access = False
            if user_id:
                rh_access_response = (
                    supabase.table("user_company_accesses")
                    .select("base_role")
                    .eq("user_id", user_id)
                    .eq("company_id", company_id)
                    .maybe_single()
                    .execute()
                )
                if rh_access_response.data:
                    current_role = rh_access_response.data.get("base_role")
                    has_access = current_role in (
                        "collaborateur_rh",
                        "rh",
                        "admin",
                    )

            available_roles = get_available_rh_roles(current_role)
            can_grant_access = True
            return EmployeeRhAccess(
                has_access=has_access,
                current_role=current_role,
                can_grant_access=can_grant_access,
                available_roles=available_roles,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la récupération de l'accès RH: {str(e)}",
            )


def get_promotion_queries() -> IPromotionQueries:
    """Factory : retourne les queries (implémentation Supabase)."""
    return PromotionQueries()


# Rétro-compatibilité : fonctions module utilisées par app.shared et employees
def list_promotions(
    company_id: str,
    year: Optional[int] = None,
    status: Optional[str] = None,
    promotion_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """Délègue au repository (pour app.shared.infrastructure.promotion et employees)."""
    from app.modules.promotions.infrastructure.repository import get_promotion_repository
    repo = get_promotion_repository()
    return repo.list(
        company_id=company_id,
        year=year,
        status=status,
        promotion_type=promotion_type,
        employee_id=employee_id,
        search=search,
        limit=limit,
        offset=offset,
    )


def get_promotion_stats(company_id: str, year: Optional[int] = None):
    """Délègue à IPromotionQueries."""
    return get_promotion_queries().get_promotion_stats(
        company_id=company_id,
        year=year,
    )


def get_employee_rh_access(employee_id: str, company_id: str):
    """Délègue à IPromotionQueries."""
    return get_promotion_queries().get_employee_rh_access(
        employee_id=employee_id,
        company_id=company_id,
    )


def get_employee_snapshot_for_promotion(
    employee_id: str,
    company_id: str,
) -> Dict[str, Optional[Any]]:
    """
    Récupère le snapshot employé + accès RH actuel pour la création d'une promotion.
    Retourne {"employee": dict, "previous_rh_access": str|None}.
    Lève HTTPException 404 si l'employé n'existe pas.
    """
    from fastapi import HTTPException
    employee_response = (
        supabase.table("employees")
        .select(
            "id, job_title, salaire_de_base, statut, classification_conventionnelle, contract_type, user_id"
        )
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .single()
        .execute()
    )
    if not employee_response.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé")
    employee = employee_response.data
    previous_rh_access = None
    if employee.get("user_id"):
        rh_response = (
            supabase.table("user_company_accesses")
            .select("base_role")
            .eq("user_id", employee["user_id"])
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if rh_response.data:
            previous_rh_access = rh_response.data.get("base_role")
    return {"employee": employee, "previous_rh_access": previous_rh_access}


def get_employee_data_for_document(employee_id: str) -> Dict[str, Any]:
    """Données employé pour génération document (PDF promotion). Lève 404 si absent."""
    from fastapi import HTTPException
    r = (
        supabase.table("employees")
        .select("id, first_name, last_name, job_title, employee_folder_name")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Employé non trouvé")
    return r.data


def get_company_data_for_document(company_id: str) -> Dict[str, Any]:
    """Données entreprise pour génération document (PDF promotion). Lève 404 si absente."""
    from fastapi import HTTPException
    r = (
        supabase.table("companies")
        .select(
            "id, company_name, raison_sociale, adresse_rue, adresse_ville, adresse_code_postal, siret"
        )
        .eq("id", company_id)
        .single()
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Entreprise non trouvée")
    return r.data


__all__ = [
    "PromotionQueries",
    "get_promotion_queries",
    "list_promotions",
    "get_promotion_stats",
    "get_employee_rh_access",
    "get_employee_snapshot_for_promotion",
    "get_employee_data_for_document",
    "get_company_data_for_document",
]
