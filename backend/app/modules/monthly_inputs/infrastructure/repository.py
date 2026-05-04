"""
Repository monthly_inputs : implémentation IMonthlyInputsRepository.

Accès Supabase table monthly_inputs. Comportement identique à api/routers/monthly_inputs.py.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.monthly_inputs.domain.interfaces import IMonthlyInputsRepository


class SupabaseMonthlyInputsRepository(IMonthlyInputsRepository):
    """Implémentation Supabase pour table monthly_inputs."""

    def list_by_period(self, year: int, month: int) -> List[Dict[str, Any]]:
        response = (
            supabase.table("monthly_inputs")
            .select("*")
            .match({"year": year, "month": month})
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    def list_by_employee_period(
        self, employee_id: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        response = (
            supabase.table("monthly_inputs")
            .select("*")
            .match({"employee_id": employee_id, "year": year, "month": month})
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    def get_company_ids_by_employee_ids(
        self, employee_ids: List[str]
    ) -> Dict[str, str]:
        """Retourne {employee_id: company_id} pour les employés trouvés (company_id non null)."""
        if not employee_ids:
            return {}
        response = (
            supabase.table("employees")
            .select("id, company_id")
            .in_("id", employee_ids)
            .execute()
        )
        out: Dict[str, str] = {}
        for row in response.data or []:
            eid = row.get("id")
            cid = row.get("company_id")
            if eid is not None and cid is not None:
                out[str(eid)] = str(cid)
        return out

    def insert_batch(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        response = supabase.table("monthly_inputs").insert(rows).execute()
        return response.data or []

    def insert_one(self, row: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("monthly_inputs").insert(row).execute()
        if not response.data:
            return {}
        return response.data[0]

    def delete_by_id(self, input_id: str) -> None:
        supabase.table("monthly_inputs").delete().eq("id", input_id).execute()

    def delete_by_id_and_employee(self, input_id: str, employee_id: str) -> None:
        (
            supabase.table("monthly_inputs")
            .delete()
            .eq("id", input_id)
            .eq("employee_id", employee_id)
            .execute()
        )


monthly_inputs_repository = SupabaseMonthlyInputsRepository()
