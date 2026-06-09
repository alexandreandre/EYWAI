"""Persistance company_jei_settings via Supabase."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.jei_settings.domain.interfaces import AbstractJeiSettingsRepository


class SupabaseJeiSettingsRepository(AbstractJeiSettingsRepository):
    """Lecture / upsert sur company_jei_settings."""

    def get_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("company_jei_settings")
            .select("*")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        payload.pop("created_at", None)
        if payload.get("id") is None:
            payload.pop("id", None)
        res = (
            supabase.table("company_jei_settings")
            .upsert(payload, on_conflict="company_id")
            .execute()
        )
        if not res.data:
            raise RuntimeError("Upsert company_jei_settings sans données retournées")
        row = res.data[0] if isinstance(res.data, list) else res.data
        return row


jei_settings_repository = SupabaseJeiSettingsRepository()
