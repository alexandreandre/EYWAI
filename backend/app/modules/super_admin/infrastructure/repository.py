"""
Repository super_admin : accès table super_admins.

Implémente l'accès lecture Supabase pour super_admins.
"""

from __future__ import annotations

from typing import List, Optional, Union
from uuid import UUID

from app.core.database import get_supabase_client

from app.modules.super_admin.domain.entities import SuperAdmin
from app.modules.super_admin.infrastructure.mappers import row_to_super_admin


def get_by_user_id(user_id: Union[UUID, str]) -> Optional[SuperAdmin]:
    """Retourne le super admin actif pour ce user_id, ou None."""
    supabase = get_supabase_client()
    uid = str(user_id) if isinstance(user_id, UUID) else user_id
    result = (
        supabase.table("super_admins")
        .select("*")
        .eq("user_id", uid)
        .eq("is_active", True)
        .execute()
    )
    if not result.data or len(result.data) == 0:
        return None
    return row_to_super_admin(result.data[0])


def list_all() -> List[SuperAdmin]:
    """Liste tous les super admins (ordre created_at desc)."""
    supabase = get_supabase_client()
    result = (
        supabase.table("super_admins")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return [row_to_super_admin(row) for row in (result.data or [])]
