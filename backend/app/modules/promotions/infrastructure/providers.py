"""
Providers (services externes) du module promotions.

- IPromotionDocumentProvider : génération et stockage PDF (implémentation locale sous app/*).
- IEmployeeUpdater : application des changements promotion sur employé et accès RH (Supabase).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.promotions.domain.enums import RhAccessRole
from app.modules.promotions.domain.interfaces import (
    IEmployeeUpdater,
    IPromotionDocumentProvider,
    PromotionApplyProtocol,
)
from app.modules.promotions.infrastructure.document_generator import (
    generate_promotion_letter,
    get_promotion_pdf_stream,
    save_promotion_document,
)


class PromotionDocumentProviderLegacyWrapper(IPromotionDocumentProvider):
    """Implémentation locale : délègue à document_generator (app/*, sans legacy)."""

    def generate_letter(
        self,
        promotion_data: Dict[str, Any],
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
        logo_path: Optional[str] = None,
    ) -> bytes:
        return generate_promotion_letter(
            promotion_data=promotion_data,
            employee_data=employee_data,
            company_data=company_data,
            logo_path=logo_path,
        )

    def save_document(
        self,
        promotion_id: str,
        company_id: str,
        employee_id: str,
        employee_folder_name: str,
        pdf_bytes: bytes,
    ) -> str:
        return save_promotion_document(
            promotion_id=promotion_id,
            company_id=company_id,
            employee_id=employee_id,
            employee_folder_name=employee_folder_name,
            pdf_bytes=pdf_bytes,
        )

    def get_pdf_stream(self, promotion_id: str, company_id: str) -> Any:
        return get_promotion_pdf_stream(
            promotion_id=promotion_id,
            company_id=company_id,
        )


class EmployeeUpdater(IEmployeeUpdater):
    """Implémentation Supabase du port IEmployeeUpdater (employés, user_company_accesses)."""

    def apply_promotion_changes(
        self,
        promotion: PromotionApplyProtocol,
        company_id: str,
    ) -> None:
        try:
            update_data = {}
            if promotion.new_job_title:
                update_data["job_title"] = promotion.new_job_title
            if promotion.new_salary:
                update_data["salaire_de_base"] = promotion.new_salary
            if promotion.new_statut:
                update_data["statut"] = promotion.new_statut
            if promotion.new_classification:
                update_data["classification_conventionnelle"] = (
                    promotion.new_classification
                )

            if update_data:
                response = (
                    supabase.table("employees")
                    .update(update_data)
                    .eq("id", promotion.employee_id)
                    .eq("company_id", company_id)
                    .execute()
                )
                if not response.data:
                    raise HTTPException(
                        status_code=500,
                        detail="Échec de la mise à jour de l'employé",
                    )

            if promotion.grant_rh_access and promotion.new_rh_access:
                self.update_employee_rh_access(
                    promotion.employee_id,
                    company_id,
                    promotion.new_rh_access,
                    promotion.id,
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de l'application des changements: {str(e)}",
            )

    def update_employee_rh_access(
        self,
        employee_id: str,
        company_id: str,
        new_rh_access: RhAccessRole,
        promotion_id: str,
    ) -> None:
        try:
            employee_response = (
                supabase.table("employees")
                .select("id, user_id, contract_type, statut")
                .eq("id", employee_id)
                .eq("company_id", company_id)
                .single()
                .execute()
            )
            if not employee_response.data:
                raise HTTPException(status_code=404, detail="Employé non trouvé")
            employee = employee_response.data
            user_id = employee.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="L'employé n'a pas de user_id associé. Impossible de donner des accès RH.",
                )

            current_access_response = (
                supabase.table("user_company_accesses")
                .select("id, base_role")
                .eq("user_id", user_id)
                .eq("company_id", company_id)
                .maybe_single()
                .execute()
            )
            current_access = (
                current_access_response.data if current_access_response.data else None
            )
            previous_rh_access = (
                current_access.get("base_role") if current_access else None
            )

            if previous_rh_access:
                supabase.table("promotions").update(
                    {"previous_rh_access": previous_rh_access}
                ).eq("id", promotion_id).execute()

            if current_access:
                supabase.table("user_company_accesses").update(
                    {"base_role": new_rh_access}
                ).eq("id", current_access["id"]).execute()
            else:
                other_accesses = (
                    supabase.table("user_company_accesses")
                    .select("id")
                    .eq("user_id", user_id)
                    .execute()
                )
                is_primary = len(other_accesses.data or []) == 0
                supabase.table("user_company_accesses").insert(
                    {
                        "user_id": user_id,
                        "company_id": company_id,
                        "base_role": new_rh_access,
                        "is_primary": is_primary,
                        "contract_type": employee.get("contract_type"),
                        "statut": employee.get("statut"),
                    }
                ).execute()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erreur lors de la mise à jour des accès RH: {str(e)}",
            )


def get_promotion_document_provider() -> IPromotionDocumentProvider:
    """Factory : retourne le provider document (wrapper legacy)."""
    return PromotionDocumentProviderLegacyWrapper()


def get_employee_updater() -> IEmployeeUpdater:
    """Factory : retourne l'updater employé / accès RH (implémentation Supabase)."""
    return EmployeeUpdater()
