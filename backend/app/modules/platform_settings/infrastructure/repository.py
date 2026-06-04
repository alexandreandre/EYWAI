"""Persistance Supabase — config e-mail plateforme (singleton)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger
from app.modules.platform_settings.domain.interfaces import IPlatformEmailSettingsRepository

logger = get_logger("modules.platform_settings.repository")

TABLE = "platform_email_settings"
SINGLETON_ID = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformEmailSettingsRepository(IPlatformEmailSettingsRepository):
    def get_row(self) -> Optional[Dict[str, Any]]:
        try:
            client = get_supabase_admin_client()
            resp = (
                client.table(TABLE)
                .select("*")
                .eq("id", SINGLETON_ID)
                .limit(1)
                .execute()
            )
            if resp.data:
                return resp.data[0]
        except Exception:
            logger.exception("Lecture platform_email_settings échouée")
        return None

    def upsert(self, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            client = get_supabase_admin_client()
            existing = self.get_row()
            payload = {k: v for k, v in fields.items() if v is not None or k in fields}
            payload["updated_at"] = _now_iso()
            if existing:
                resp = (
                    client.table(TABLE)
                    .update(payload)
                    .eq("id", SINGLETON_ID)
                    .execute()
                )
            else:
                payload["id"] = SINGLETON_ID
                resp = client.table(TABLE).insert(payload).execute()
            if resp.data:
                return resp.data[0]
            return self.get_row()
        except Exception:
            logger.exception("Écriture platform_email_settings échouée")
            return None


repository = PlatformEmailSettingsRepository()
