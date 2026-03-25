"""
Implémentation du port IPermissionRepository via Supabase.

Utilisée par AccessControlService. À terme, toute lecture des tables
permission_categories, permission_actions, permissions, user_permissions,
role_templates, etc. peut transiter par ce repository ou des queries dédiées.
"""

from __future__ import annotations

from app.core.database import supabase


class SupabasePermissionRepository:
    """Lecture des permissions utilisateur depuis Supabase (user_permissions, permissions)."""

    def user_has_permission(
        self,
        user_id: str,
        company_id: str,
        permission_code: str,
    ) -> bool:
        try:
            result = (
                supabase.table("user_permissions")
                .select("id, permissions(code, is_active)")
                .eq("user_id", str(user_id))
                .eq("company_id", str(company_id))
                .execute()
            )
            for row in result.data:
                perm = row.get("permissions")
                if (
                    perm
                    and perm.get("code") == permission_code
                    and perm.get("is_active", False)
                ):
                    return True
            return False
        except Exception:
            return False

    def user_has_any_rh_permission(self, user_id: str, company_id: str) -> bool:
        try:
            result = (
                supabase.table("user_permissions")
                .select("permissions(required_role, is_active)")
                .eq("user_id", str(user_id))
                .eq("company_id", str(company_id))
                .execute()
            )
            for row in result.data:
                perm = row.get("permissions")
                if perm and perm.get("is_active", False):
                    if perm.get("required_role") in ("rh", "admin"):
                        return True
            return False
        except Exception:
            return False
