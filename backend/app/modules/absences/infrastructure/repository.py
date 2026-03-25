"""
Repository absences — implémentation IAbsenceRepository.

Accès table absence_requests via Supabase. Comportement identique à l'ancien routeur.
"""

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.absences.domain.interfaces import IAbsenceRepository


class SupabaseAbsenceRepository(IAbsenceRepository):
    """Implémentation Supabase pour absence_requests."""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("absence_requests").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création de la demande.")
        return response.data[0]

    def get_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("absence_requests")
            .select("*")
            .eq("id", request_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def update(self, request_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        update_resp = (
            supabase.table("absence_requests")
            .update(data)
            .eq("id", request_id)
            .execute()
        )
        if not update_resp.data:
            return None
        r = (
            supabase.table("absence_requests")
            .select("*")
            .eq("id", request_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_by_status(self, status: Optional[str]) -> List[Dict[str, Any]]:
        query = supabase.table("absence_requests").select(
            "*, employee:employees(id, first_name, last_name)"
        )
        if status:
            query = query.eq("status", status)
        result = query.order("created_at", desc=True).execute()
        return result.data or []

    def list_validated_for_employees(
        self, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        if not employee_ids:
            return []
        result = (
            supabase.table("absence_requests")
            .select("employee_id", "type", "selected_days", "jours_payes")
            .in_("employee_id", employee_ids)
            .eq("status", "validated")
            .execute()
        )
        return result.data or []

    def list_by_employee_id(self, employee_id: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("absence_requests")
            .select("*")
            .eq("employee_id", employee_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data if result.data is not None else []


absence_repository = SupabaseAbsenceRepository()
