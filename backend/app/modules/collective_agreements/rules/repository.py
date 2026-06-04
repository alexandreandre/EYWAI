"""Persistance convention_collective_rules + journal d'extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import get_supabase_client


class CCRulesRepository:
    """Accès Supabase pour les règles CC paie."""

    def __init__(self, supabase_client: Any = None):
        self._supabase = supabase_client or get_supabase_client()

    def get_rules_by_idcc(self, idcc: str) -> Optional[dict[str, Any]]:
        try:
            response = (
                self._supabase.table("convention_collective_rules")
                .select("*")
                .eq("idcc", idcc)
                .maybe_single()
                .execute()
            )
            return response.data if response and response.data else None
        except Exception:
            return None

    def get_rules_by_agreement_id(self, agreement_id: str) -> Optional[dict[str, Any]]:
        try:
            response = (
                self._supabase.table("convention_collective_rules")
                .select("*")
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            return response.data if response and response.data else None
        except Exception:
            return None

    def upsert_rules(
        self,
        *,
        idcc: str,
        rules: dict[str, Any],
        agreement_id: Optional[str],
        schema_version: int,
        extraction_model: str,
        source_text_hash: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "idcc": idcc,
            "rules": rules,
            "agreement_id": agreement_id,
            "schema_version": schema_version,
            "extracted_at": now,
            "extraction_model": extraction_model,
            "source_text_hash": source_text_hash,
            "updated_at": now,
        }
        try:
            response = (
                self._supabase.table("convention_collective_rules")
                .upsert(payload, on_conflict="idcc")
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else payload
        except Exception as exc:
            payload["_persist_error"] = str(exc)
            return payload

    def log_extraction(
        self,
        *,
        idcc: str,
        agreement_id: Optional[str],
        status: str,
        rules_proposed: Optional[dict[str, Any]] = None,
        rules_previous: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
    ) -> dict[str, Any]:
        payload = {
            "idcc": idcc,
            "agreement_id": agreement_id,
            "status": status,
            "rules_proposed": rules_proposed,
            "rules_previous": rules_previous,
            "error_message": error_message,
            "model": model,
            "tokens_used": tokens_used,
        }
        try:
            response = (
                self._supabase.table("cc_rules_extraction_log")
                .insert(payload)
                .execute()
            )
            rows = response.data or []
            return rows[0] if rows else payload
        except Exception:
            return payload

    def get_latest_log(self, agreement_id: str) -> Optional[dict[str, Any]]:
        response = (
            self._supabase.table("cc_rules_extraction_log")
            .select("*")
            .eq("agreement_id", agreement_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

    def get_log_by_id(self, log_id: str) -> Optional[dict[str, Any]]:
        response = (
            self._supabase.table("cc_rules_extraction_log")
            .select("*")
            .eq("id", log_id)
            .maybe_single()
            .execute()
        )
        return response.data if response.data else None

    def rollback_from_log(self, log_id: str) -> Optional[dict[str, Any]]:
        log_entry = self.get_log_by_id(log_id)
        if not log_entry or log_entry.get("status") != "success":
            return None
        previous = log_entry.get("rules_previous")
        if previous is None:
            return None
        idcc = log_entry.get("idcc")
        agreement_id = log_entry.get("agreement_id")
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "idcc": idcc,
            "rules": previous,
            "agreement_id": agreement_id,
            "updated_at": now,
        }
        response = (
            self._supabase.table("convention_collective_rules")
            .upsert(payload, on_conflict="idcc")
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else payload

    def list_catalog_by_idcc(self, idcc: str) -> Optional[dict[str, Any]]:
        try:
            response = (
                self._supabase.table("collective_agreements_catalog")
                .select("*")
                .eq("idcc", idcc)
                .eq("is_active", True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            return response.data if response and response.data else None
        except Exception:
            return None

    def list_all_active_catalog(self) -> list[dict[str, Any]]:
        response = (
            self._supabase.table("collective_agreements_catalog")
            .select("*")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return list(response.data or [])
