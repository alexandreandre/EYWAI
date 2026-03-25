"""
Repository collective_agreements : persistance catalogue et assignations.

Implémentation des accès DB (Supabase). Lève domain.exceptions.
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.core.database import get_supabase_client
from app.modules.collective_agreements.domain.exceptions import (
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.infrastructure.mappers import serialize_dates
from app.modules.collective_agreements.infrastructure.queries import (
    get_classifications_for_idcc,
)

SELECT_AGREEMENT_DETAILS = (
    "*, agreement_details:collective_agreement_id(id, name, idcc, description, sector, "
    "rules_pdf_path, rules_pdf_filename, effective_date, is_active, created_at, updated_at)"
)


class CollectiveAgreementRepository:
    """Implémentation de ICollectiveAgreementRepository."""

    def __init__(self, supabase_client: Any = None):
        self._supabase = supabase_client or get_supabase_client()

    def list_catalog(
        self,
        *,
        sector: Optional[str] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> List[dict[str, Any]]:
        query = self._supabase.table("collective_agreements_catalog").select("*")
        if active_only:
            query = query.eq("is_active", True)
        if sector:
            query = query.eq("sector", sector)
        if search:
            query = query.or_(f"name.ilike.%{search}%,idcc.ilike.%{search}%")
        query = query.order("name")
        response = query.execute()
        return list(response.data or [])

    def get_catalog_item(self, agreement_id: str) -> Optional[dict[str, Any]]:
        response = (
            self._supabase.table("collective_agreements_catalog")
            .select("*")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        return response.data if response.data else None

    def get_catalog_item_rules_path(self, agreement_id: str) -> Optional[str]:
        response = (
            self._supabase.table("collective_agreements_catalog")
            .select("rules_pdf_path")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        return response.data.get("rules_pdf_path") if response.data else None

    def get_classifications_for_agreement(self, agreement_id: str) -> List[Any]:
        item = self.get_catalog_item(agreement_id)
        if not item:
            raise NotFoundError("Convention collective non trouvée")
        return get_classifications_for_idcc(self._supabase, item.get("idcc") or "")

    def create_catalog_item(self, data: dict[str, Any]) -> dict[str, Any]:
        db_data = serialize_dates(data)
        response = (
            self._supabase.table("collective_agreements_catalog")
            .insert(db_data)
            .execute()
        )
        if not response.data:
            raise ValidationError("Échec de la création")
        return response.data[0]

    def update_catalog_item(
        self, agreement_id: str, data: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        current = (
            self._supabase.table("collective_agreements_catalog")
            .select("rules_pdf_path")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        if not current.data:
            raise NotFoundError("Convention collective non trouvée")
        if not data:
            raise ValidationError("Aucune donnée à mettre à jour")
        update_data = serialize_dates(data)
        response = (
            self._supabase.table("collective_agreements_catalog")
            .update(update_data)
            .eq("id", agreement_id)
            .execute()
        )
        if not response.data:
            raise NotFoundError("Convention collective non trouvée")
        return response.data[0]

    def delete_catalog_item(self, agreement_id: str) -> bool:
        response = (
            self._supabase.table("collective_agreements_catalog")
            .delete()
            .eq("id", agreement_id)
            .execute()
        )
        if not response.data:
            raise NotFoundError("Convention collective non trouvée")
        return True

    def get_my_company_assignments(self, company_id: str) -> List[dict[str, Any]]:
        response = (
            self._supabase.table("company_collective_agreements")
            .select(SELECT_AGREEMENT_DETAILS)
            .eq("company_id", company_id)
            .execute()
        )
        return list(response.data or [])

    def assign_to_company(
        self, company_id: str, collective_agreement_id: str, assigned_by: str
    ) -> dict[str, Any]:
        assignment_data = {
            "company_id": company_id,
            "collective_agreement_id": collective_agreement_id,
            "assigned_by": assigned_by,
        }
        response = (
            self._supabase.table("company_collective_agreements")
            .insert(assignment_data)
            .execute()
        )
        if not response.data:
            raise ValidationError("Échec de l'assignation")
        return response.data[0]

    def unassign_from_company(self, assignment_id: str, company_id: str) -> bool:
        response = (
            self._supabase.table("company_collective_agreements")
            .delete()
            .eq("id", assignment_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not response.data:
            raise NotFoundError("Assignation non trouvée ou non autorisée")
        return True

    def get_all_assignments_by_company(self) -> List[dict[str, Any]]:
        companies_response = (
            self._supabase.table("companies").select("id, company_name").execute()
        )
        if not companies_response.data:
            return []
        result = []
        for company in companies_response.data:
            assignments_response = (
                self._supabase.table("company_collective_agreements")
                .select(SELECT_AGREEMENT_DETAILS)
                .eq("company_id", company["id"])
                .execute()
            )
            result.append(
                {
                    "id": company["id"],
                    "company_name": company["company_name"],
                    "assigned_agreements": list(assignments_response.data or []),
                }
            )
        return result

    def check_assignment_exists(
        self, company_id: str, collective_agreement_id: str
    ) -> bool:
        response = (
            self._supabase.table("company_collective_agreements")
            .select("id")
            .eq("company_id", company_id)
            .eq("collective_agreement_id", collective_agreement_id)
            .maybe_single()
            .execute()
        )
        return bool(response.data)

    def get_agreement_for_chat(self, agreement_id: str) -> Optional[dict[str, Any]]:
        response = (
            self._supabase.table("collective_agreements_catalog")
            .select("id, name, idcc, description, rules_pdf_path")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        return response.data if response.data else None
