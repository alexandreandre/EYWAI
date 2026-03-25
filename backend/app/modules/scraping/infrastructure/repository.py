"""
Repository scraping : accès Supabase aux tables scraping_* et RPC get_scraping_stats.

Logique strictement persistance ; pas de règles métier.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import supabase


class ScrapingRepository:
    """Implémentation du port IScrapingRepository (Supabase)."""

    def get_scraping_stats(self) -> Dict[str, Any]:
        r = supabase.rpc("get_scraping_stats").execute()
        return r.data[0] if r.data else {}

    def get_source_by_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_sources")
            .select("*")
            .eq("id", source_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def get_source_by_key(self, source_key: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_sources")
            .select("*")
            .eq("source_key", source_key)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_sources(
        self,
        source_type: Optional[str] = None,
        is_critical: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("scraping_sources").select("*")
        if source_type:
            q = q.eq("source_type", source_type)
        if is_critical is not None:
            q = q.eq("is_critical", is_critical)
        if is_active is not None:
            q = q.eq("is_active", is_active)
        r = q.order("source_name").execute()
        return r.data or []

    def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_jobs")
            .select("*, scraping_sources(source_name, source_key)")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    def get_unread_alerts(self, limit: int = 5) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_alerts")
            .select("*, scraping_sources(source_name, source_key)")
            .eq("is_read", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    def get_critical_sources(self) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_sources")
            .select("*")
            .eq("is_critical", True)
            .eq("is_active", True)
            .execute()
        )
        return r.data or []

    def get_last_job_for_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_jobs")
            .select("*")
            .eq("source_id", source_id)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def get_jobs_for_source_30d(
        self, source_id: str
    ) -> tuple[List[Dict[str, Any]], int]:
        since = (datetime.now() - timedelta(days=30)).isoformat()
        r = (
            supabase.table("scraping_jobs")
            .select("success", count="exact")
            .eq("source_id", source_id)
            .gte("created_at", since)
            .execute()
        )
        return (r.data or []), (r.count or 0)

    def get_unresolved_alerts_count(self, source_id: str) -> int:
        r = (
            supabase.table("scraping_alerts")
            .select("id", count="exact")
            .eq("source_id", source_id)
            .eq("is_resolved", False)
            .execute()
        )
        return r.count or 0

    def get_jobs_history_for_source(
        self, source_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_jobs")
            .select("*")
            .eq("source_id", source_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    def get_schedules_for_source(self, source_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_schedules")
            .select("*")
            .eq("source_id", source_id)
            .execute()
        )
        return r.data or []

    def get_recent_alerts_for_source(
        self, source_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("scraping_alerts")
            .select("*")
            .eq("source_id", source_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return r.data or []

    def list_jobs(
        self,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("scraping_jobs").select(
            "*, scraping_sources(source_name, source_key)"
        )
        if source_id:
            q = q.eq("source_id", source_id)
        if status:
            q = q.eq("status", status)
        if success is not None:
            q = q.eq("success", success)
        r = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return r.data or []

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_jobs")
            .select("*, scraping_sources(*)")
            .eq("id", job_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def get_job_logs_fields(self, job_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_jobs")
            .select("id, status, execution_logs, success, error_message, completed_at")
            .eq("id", job_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def create_job(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("scraping_jobs").insert(data).execute()
        return r.data[0]

    def update_job(self, job_id: str, data: Dict[str, Any]) -> None:
        supabase.table("scraping_jobs").update(data).eq("id", job_id).execute()

    def create_alert(self, data: Dict[str, Any]) -> None:
        supabase.table("scraping_alerts").insert(data).execute()

    def list_schedules(
        self,
        is_enabled: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("scraping_schedules").select(
            "*, scraping_sources(source_name, source_key)"
        )
        if is_enabled is not None:
            q = q.eq("is_enabled", is_enabled)
        r = q.order("next_run_at").execute()
        return r.data or []

    def create_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("scraping_schedules").insert(data).execute()
        return r.data[0]

    def update_schedule(
        self, schedule_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("scraping_schedules")
            .update(data)
            .eq("id", schedule_id)
            .execute()
        )
        return r.data[0] if r.data else None

    def delete_schedule(self, schedule_id: str) -> bool:
        r = (
            supabase.table("scraping_schedules")
            .delete()
            .eq("id", schedule_id)
            .execute()
        )
        return bool(r.data)

    def list_alerts(
        self,
        is_read: Optional[bool] = None,
        is_resolved: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("scraping_alerts").select(
            "*, scraping_sources(source_name, source_key)"
        )
        if is_read is not None:
            q = q.eq("is_read", is_read)
        if is_resolved is not None:
            q = q.eq("is_resolved", is_resolved)
        if severity:
            q = q.eq("severity", severity)
        r = q.order("created_at", desc=True).limit(limit).execute()
        return r.data or []

    def mark_alert_read(self, alert_id: str) -> bool:
        r = (
            supabase.table("scraping_alerts")
            .update({"is_read": True})
            .eq("id", alert_id)
            .execute()
        )
        return bool(r.data)

    def resolve_alert(self, alert_id: str, data: Dict[str, Any]) -> bool:
        r = supabase.table("scraping_alerts").update(data).eq("id", alert_id).execute()
        return bool(r.data)
