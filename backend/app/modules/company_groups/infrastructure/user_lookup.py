"""
Recherche utilisateur par email et récupération des emails (auth.admin).
Implémente IUserLookupProvider. Comportement identique aux usages dans les routeurs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client

from app.modules.company_groups.domain.interfaces import IUserLookupProvider


class SupabaseUserLookupProvider(IUserLookupProvider):
    """Implémentation via Supabase Auth Admin API."""

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Recherche un utilisateur par email via auth.admin.list_users()."""
        client = get_supabase_admin_client()
        try:
            users = client.auth.admin.list_users()
            for u in users:
                if getattr(u, "email", None) == email:
                    return {"id": str(u.id), "email": email}
        except Exception:
            pass
        return None

    def get_user_emails_map(self, user_ids: List[str]) -> Dict[str, str]:
        """Retourne un dict user_id -> email via auth.admin.list_users()."""
        if not user_ids:
            return {}
        client = get_supabase_admin_client()
        out = {}
        try:
            users = client.auth.admin.list_users()
            for u in users:
                uid = str(getattr(u, "id", ""))
                if uid in user_ids:
                    out[uid] = getattr(u, "email", uid)
        except Exception:
            pass
        return out


user_lookup_provider = SupabaseUserLookupProvider()
