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
