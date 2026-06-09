from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.badgeuse.infrastructure.db_errors import execute_supabase


def _maybe_single_row(result: Any) -> Optional[Dict[str, Any]]:
    if not result:
        return None
    data = result.data
    if data is None:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


class TerminalDevicesRepository:
    table_name = "badgeuse_terminal_devices"

    def count_active(self, company_id: str) -> int:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("id", count="exact")
            .eq("company_id", company_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return int(result.count or 0)

    def list_devices(self, company_id: str) -> List[Dict[str, Any]]:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select(
                "id, company_id, label, token_prefix, created_by, "
                "last_used_at, revoked_at, created_at"
            )
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(result.data or [])

    def get_by_token_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("*")
            .eq("token_hash", token_hash)
            .is_("revoked_at", "null")
            .maybe_single()
            .execute()
        )
        return _maybe_single_row(result)

    def create_device(
        self,
        *,
        company_id: str,
        label: str,
        token_hash: str,
        token_prefix: str,
        created_by: str,
    ) -> Dict[str, Any]:
        payload = {
            "company_id": company_id,
            "label": label.strip(),
            "token_hash": token_hash,
            "token_prefix": token_prefix,
            "created_by": created_by,
        }
        result = execute_supabase(
            lambda: supabase.table(self.table_name).insert(payload).execute()
        )
        row = _maybe_single_row(result)
        if not row:
            raise RuntimeError("Création du terminal impossible")
        return row

    def revoke_device(self, *, device_id: str, company_id: str) -> None:
        now = datetime.utcnow().isoformat()
        execute_supabase(
            lambda: supabase.table(self.table_name)
            .update({"revoked_at": now})
            .eq("id", device_id)
            .eq("company_id", company_id)
            .is_("revoked_at", "null")
            .execute()
        )

    def touch_last_used(self, device_id: str) -> None:
        now = datetime.utcnow().isoformat()
        execute_supabase(
            lambda: supabase.table(self.table_name)
            .update({"last_used_at": now})
            .eq("id", device_id)
            .execute()
        )
