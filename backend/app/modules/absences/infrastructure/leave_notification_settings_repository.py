"""Persistance des paramètres email pour demandes de congés."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase

TABLE = "company_leave_notification_settings"


DEFAULT_LEAVE_NOTIFICATION_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "notify_on_employee_request": True,
    "notify_after_manager_approval": True,
    "recipient_roles": ["rh", "admin"],
    "extra_recipient_emails": [],
}


def get_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table(TABLE)
        .select("*")
        .eq("company_id", str(company_id))
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def get_effective_settings(company_id: str) -> tuple[dict[str, Any], bool]:
    row = get_row(company_id)
    if not row:
        return {**DEFAULT_LEAVE_NOTIFICATION_SETTINGS, "company_id": company_id}, False
    merged = {**DEFAULT_LEAVE_NOTIFICATION_SETTINGS, **row, "company_id": company_id}
    return merged, True


def upsert(company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_row(company_id)
    payload = {**data, "company_id": company_id, "updated_at": now}
    if existing:
        resp = (
            supabase.table(TABLE).update(payload).eq("company_id", company_id).execute()
        )
    else:
        payload["created_at"] = now
        resp = supabase.table(TABLE).insert(payload).execute()
    if not resp.data:
        raise RuntimeError(
            "Upsert company_leave_notification_settings sans données retournées"
        )
    return resp.data[0] if isinstance(resp.data, list) else resp.data
