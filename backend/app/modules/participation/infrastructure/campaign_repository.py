"""Repository campagnes bulletin d'option participation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ParticipationCampaignRepository:
    def create_campaign(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "updated_at": _now_iso()}
        result = supabase.table("participation_campaigns").insert(payload).execute()
        if not result.data:
            raise RuntimeError("Insert campaign returned no data")
        return dict(result.data[0])

    def get_campaign(self, campaign_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        result = (
            supabase.table("participation_campaigns")
            .select("*")
            .eq("id", campaign_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = result.data if result else None
        return dict(row) if row else None

    def list_campaigns(
        self, company_id: str, year: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table("participation_campaigns")
            .select("*")
            .eq("company_id", company_id)
            .order("year", desc=True)
            .order("created_at", desc=True)
        )
        if year is not None:
            query = query.eq("year", year)
        result = query.execute()
        return [dict(r) for r in (result.data or [])]

    def update_campaign(self, campaign_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**patch, "updated_at": _now_iso()}
        result = (
            supabase.table("participation_campaigns")
            .update(payload)
            .eq("id", campaign_id)
            .execute()
        )
        if not result.data:
            raise LookupError("Campagne introuvable")
        return dict(result.data[0])

    def upsert_advances(
        self, campaign_id: str, advances: List[Dict[str, Any]]
    ) -> None:
        if not advances:
            return
        rows = [{**a, "campaign_id": campaign_id} for a in advances]
        supabase.table("participation_campaign_advances").upsert(
            rows, on_conflict="campaign_id,employee_id"
        ).execute()

    def list_advances(self, campaign_id: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("participation_campaign_advances")
            .select("*")
            .eq("campaign_id", campaign_id)
            .execute()
        )
        return [dict(r) for r in (result.data or [])]

    def insert_bulletins(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        result = supabase.table("participation_bulletins").insert(rows).execute()
        return [dict(r) for r in (result.data or [])]

    def list_bulletins(
        self,
        campaign_id: str,
        *,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table("participation_bulletins")
            .select("*, employees(first_name, last_name)")
            .eq("campaign_id", campaign_id)
            .order("created_at")
        )
        if employee_id:
            query = query.eq("employee_id", employee_id)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return [dict(r) for r in (result.data or [])]

    def get_bulletin(
        self, bulletin_id: str, *, company_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        query = supabase.table("participation_bulletins").select("*").eq("id", bulletin_id)
        if company_id:
            query = query.eq("company_id", company_id)
        result = query.maybe_single().execute()
        row = result.data if result else None
        return dict(row) if row else None

    def get_bulletin_for_employee(
        self, bulletin_id: str, employee_id: str
    ) -> Optional[Dict[str, Any]]:
        result = (
            supabase.table("participation_bulletins")
            .select("*")
            .eq("id", bulletin_id)
            .eq("employee_id", employee_id)
            .maybe_single()
            .execute()
        )
        row = result.data if result else None
        return dict(row) if row else None

    def list_bulletins_for_employee(
        self, employee_id: str, company_id: str
    ) -> List[Dict[str, Any]]:
        result = (
            supabase.table("participation_bulletins")
            .select("*, participation_campaigns(year, exercise_label, deadline_at, status)")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [dict(r) for r in (result.data or [])]

    def update_bulletin(self, bulletin_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**patch, "updated_at": _now_iso()}
        result = (
            supabase.table("participation_bulletins")
            .update(payload)
            .eq("id", bulletin_id)
            .execute()
        )
        if not result.data:
            raise LookupError("Bulletin introuvable")
        return dict(result.data[0])

    def count_bulletins_by_status(self, campaign_id: str) -> Dict[str, int]:
        rows = self.list_bulletins(campaign_id)
        counts: Dict[str, int] = {}
        for row in rows:
            st = str(row.get("status") or "pending")
            counts[st] = counts.get(st, 0) + 1
        return counts


campaign_repository = ParticipationCampaignRepository()
