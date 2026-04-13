from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase


class SupabaseSupportRepository:
    """Accès table support_tickets et support_ticket_status_history via Supabase."""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("support_tickets").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création du ticket support.")
        return response.data[0]

    def get_by_id(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("support_tickets")
            .select("*")
            .eq("id", ticket_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def list_for_super_admin(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = (
            supabase.table("support_tickets")
            .select("*, companies(company_name)")
            .order("created_at", desc=True)
        )
        if filters.get("company_id"):
            query = query.eq("company_id", filters["company_id"])
        if filters.get("urgency"):
            query = query.eq("urgency", filters["urgency"])
        if filters.get("status"):
            query = query.eq("status", filters["status"])
        if filters.get("module"):
            query = query.eq("module", filters["module"])
        if filters.get("date_from") is not None:
            query = query.gte("created_at", filters["date_from"])
        if filters.get("date_to") is not None:
            query = query.lte("created_at", filters["date_to"])
        result = query.execute()
        return result.data or []

    def list_for_company(self, company_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = (
            supabase.table("support_tickets")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
        )
        if filters.get("urgency"):
            query = query.eq("urgency", filters["urgency"])
        if filters.get("status"):
            query = query.eq("status", filters["status"])
        if filters.get("module"):
            query = query.eq("module", filters["module"])
        if filters.get("date_from") is not None:
            query = query.gte("created_at", filters["date_from"])
        if filters.get("date_to") is not None:
            query = query.lte("created_at", filters["date_to"])
        if filters.get("user_id"):
            query = query.eq("user_id", filters["user_id"])
        result = query.execute()
        return result.data or []

    def list_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("support_tickets")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def update_status(self, ticket_id: str, new_status: str) -> Optional[Dict[str, Any]]:
        from datetime import datetime, timezone

        supabase.table("support_tickets").update(
            {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", ticket_id).execute()
        r = (
            supabase.table("support_tickets")
            .select("*")
            .eq("id", ticket_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def get_status_history(self, ticket_id: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("support_ticket_status_history")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("changed_at", desc=False)
            .execute()
        )
        return result.data or []

    def add_status_history(self, data: Dict[str, Any]) -> None:
        supabase.table("support_ticket_status_history").insert(data).execute()


support_repository = SupabaseSupportRepository()
