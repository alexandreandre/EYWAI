from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from app.core.database import supabase
from app.modules.badgeuse.infrastructure.db_errors import execute_supabase


def _maybe_single_row(result: Any) -> Optional[Dict[str, Any]]:
    """PostgREST + maybe_single : .execute() peut renvoyer None si aucune ligne."""
    if not result:
        return None
    data = result.data
    if data is None:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _first_mutation_row(result: Any) -> Optional[Dict[str, Any]]:
    if not result:
        return None
    data = result.data
    if data is None:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


class BadgeCredentialsRepository:
    table_name = "employee_badge_credentials"

    def get_credentials(
        self, *, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("*")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return _maybe_single_row(result)

    def ensure_credentials(
        self, *, employee_id: str, company_id: str
    ) -> Dict[str, Any]:
        existing = self.get_credentials(
            employee_id=employee_id, company_id=company_id
        )
        if existing and not existing.get("revoked_at"):
            return existing

        now = datetime.utcnow().isoformat()
        payload = {
            "employee_id": employee_id,
            "company_id": company_id,
            "token_version": 1,
            "secret_salt": str(uuid.uuid4()),
            "revoked_at": None,
            "updated_at": now,
        }
        if existing:
            result = execute_supabase(
                lambda: supabase.table(self.table_name)
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
            row = _first_mutation_row(result)
            if row:
                return row
        else:
            payload["created_at"] = now
            result = execute_supabase(
                lambda: supabase.table(self.table_name).insert(payload).execute()
            )
            row = _first_mutation_row(result)
            if row:
                return row
        raise RuntimeError("Impossible de créer les credentials badge")

    def regenerate_credentials(
        self, *, employee_id: str, company_id: str
    ) -> Dict[str, Any]:
        existing = self.get_credentials(
            employee_id=employee_id, company_id=company_id
        )
        now = datetime.utcnow().isoformat()
        new_version = int((existing or {}).get("token_version") or 0) + 1
        payload = {
            "employee_id": employee_id,
            "company_id": company_id,
            "token_version": new_version,
            "secret_salt": str(uuid.uuid4()),
            "revoked_at": None,
            "updated_at": now,
        }
        if existing:
            result = execute_supabase(
                lambda: supabase.table(self.table_name)
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
            row = _first_mutation_row(result)
            if row:
                return row
        payload["created_at"] = now
        result = execute_supabase(
            lambda: supabase.table(self.table_name).insert(payload).execute()
        )
        row = _first_mutation_row(result)
        if not row:
            raise RuntimeError("Impossible de régénérer le badge")
        return row


badge_credentials_repository = BadgeCredentialsRepository()
