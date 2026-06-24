"""Dépendances FastAPI — import admin (super-admin)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.dsn_import.api.dependencies import verify_super_admin


def super_admin_auth_user_id(super_admin: Dict[str, Any]) -> Optional[str]:
    """UUID auth.users — pas l'id ligne super_admins."""
    raw = super_admin.get("user_id")
    return str(raw) if raw else None


__all__ = ["super_admin_auth_user_id", "verify_super_admin"]
