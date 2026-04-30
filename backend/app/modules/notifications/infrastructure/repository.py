"""Persistance Supabase — notifications."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.database import supabase


class SupabaseNotificationsRepository:
    def get_for_employee(
        self,
        employee_id: str,
        company_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        SELECT * FROM notifications
        WHERE employee_id = ... AND company_id = ...
        ORDER BY created_at DESC
        LIMIT limit
        """
        r = (
            supabase.table("notifications")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return (r.data or []) if r else []

    def get_unread_count(self, employee_id: str, company_id: str) -> int:
        """COUNT WHERE is_read = false."""
        resp = (
            supabase.table("notifications")
            .select("id", count="exact")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .eq("is_read", False)
            .execute()
        )
        return resp.count or 0

    def mark_as_read(self, notification_id: str, employee_id: str) -> bool:
        """
        UPDATE notifications SET is_read = true
        WHERE id = notification_id AND employee_id = employee_id
        """
        upd = (
            supabase.table("notifications")
            .update({"is_read": True})
            .eq("id", notification_id)
            .eq("employee_id", employee_id)
            .execute()
        )
        rows = upd.data if upd else None
        if isinstance(rows, list):
            return len(rows) > 0
        if isinstance(rows, dict):
            return True
        return False

    def mark_all_as_read(self, employee_id: str, company_id: str) -> bool:
        """
        UPDATE notifications SET is_read = true
        WHERE employee_id = ... AND company_id = ...
          AND is_read = false
        """
        upd = (
            supabase.table("notifications")
            .update({"is_read": True})
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .eq("is_read", False)
            .execute()
        )
        return upd.data is not None


notifications_repository = SupabaseNotificationsRepository()
