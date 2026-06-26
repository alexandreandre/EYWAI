"""Utilisateur système pour les flux DSN (initiated_by des sorties)."""

from __future__ import annotations

from typing import Optional

from app.core.database import get_supabase_admin_client

_FALLBACK_USER_ID: Optional[str] = None


def resolve_dsn_workflow_user_id(current_user_id: Optional[str] = None) -> str:
    """UUID Auth valide pour initiated_by (commit DSN, rattrapages)."""
    if current_user_id:
        return str(current_user_id)
    global _FALLBACK_USER_ID
    if _FALLBACK_USER_ID:
        return _FALLBACK_USER_ID
    resp = (
        get_supabase_admin_client()
        .table("super_admins")
        .select("user_id")
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows or not rows[0].get("user_id"):
        raise RuntimeError(
            "Impossible de résoudre initiated_by pour le flux DSN (super_admins vide)."
        )
    _FALLBACK_USER_ID = str(rows[0]["user_id"])
    return _FALLBACK_USER_ID
