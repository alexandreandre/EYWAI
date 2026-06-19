"""Repository Supabase pour staging import pointages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client, supabase

BATCHES = "schedule_import_batches"
ITEMS = "schedule_import_items"
PROFILES = "company_timesheet_import_profiles"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _admin():
    return get_supabase_admin_client()


class TimesheetImportRepository:
    def batch_exists_by_hash_committed(self, company_id: str, file_hash: str) -> bool:
        resp = (
            _admin()
            .table(BATCHES)
            .select("id")
            .eq("company_id", company_id)
            .eq("file_hash", file_hash)
            .eq("status", "committed")
            .limit(1)
            .execute()
        )
        return bool(resp.data)

    def find_recent_preview_by_hash(
        self,
        company_id: str,
        file_hash: str,
        *,
        period_year: int,
        period_month: int,
        max_age_hours: int = 24,
    ) -> Optional[Dict[str, Any]]:
        resp = (
            _admin()
            .table(BATCHES)
            .select("*")
            .eq("company_id", company_id)
            .eq("file_hash", file_hash)
            .eq("period_year", period_year)
            .eq("period_month", period_month)
            .in_("status", ["previewed", "parsed"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        row = resp.data[0]
        created = row.get("created_at")
        if created:
            try:
                from datetime import timedelta

                ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - ts > timedelta(hours=max_age_hours):
                    return None
            except ValueError:
                pass
        return row

    def insert_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**payload, "updated_at": _now_iso()}
        resp = _admin().table(BATCHES).insert(payload).execute()
        if not resp.data:
            raise RuntimeError("Impossible de créer le batch d'import.")
        return resp.data[0]

    def update_batch(self, batch_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**payload, "updated_at": _now_iso()}
        resp = (
            _admin()
            .table(BATCHES)
            .update(payload)
            .eq("id", batch_id)
            .execute()
        )
        return (resp.data or [{}])[0]

    def get_batch(
        self, batch_id: str, *, company_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        q = _admin().table(BATCHES).select("*").eq("id", batch_id)
        if company_id:
            q = q.eq("company_id", company_id)
        resp = q.maybe_single().execute()
        return resp.data

    def insert_items(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        chunk = 200
        for i in range(0, len(items), chunk):
            _admin().table(ITEMS).insert(items[i : i + chunk]).execute()

    def list_items(self, batch_id: str) -> List[Dict[str, Any]]:
        resp = (
            _admin()
            .table(ITEMS)
            .select("*")
            .eq("batch_id", batch_id)
            .order("row_index")
            .execute()
        )
        return resp.data or []

    def delete_items(self, batch_id: str) -> None:
        _admin().table(ITEMS).delete().eq("batch_id", batch_id).execute()

    def list_profiles(self, company_id: str) -> List[Dict[str, Any]]:
        resp = (
            supabase.table(PROFILES)
            .select("*")
            .eq("company_id", company_id)
            .order("profile_name")
            .execute()
        )
        return resp.data or []

    def upsert_profile(
        self, company_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        row = {
            **payload,
            "company_id": company_id,
            "updated_at": _now_iso(),
        }
        resp = (
            supabase.table(PROFILES)
            .upsert(
                row,
                on_conflict="company_id,profile_name,source_type",
            )
            .execute()
        )
        return (resp.data or [{}])[0]

    def get_profile(
        self, company_id: str, profile_name: str, source_type: str
    ) -> Optional[Dict[str, Any]]:
        resp = (
            supabase.table(PROFILES)
            .select("*")
            .eq("company_id", company_id)
            .eq("profile_name", profile_name)
            .eq("source_type", source_type)
            .maybe_single()
            .execute()
        )
        return resp.data


timesheet_import_repository = TimesheetImportRepository()

__all__ = ["TimesheetImportRepository", "timesheet_import_repository"]
