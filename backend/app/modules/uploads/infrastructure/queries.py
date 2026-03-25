"""
Vérifications d'autorisation pour les uploads logos.

Implémente ILogoPermissionChecker (domain). Comportement identique à api/routers/uploads.py.
"""

from __future__ import annotations

from app.core.database import supabase

from app.modules.uploads.domain.interfaces import ILogoPermissionChecker


class LogoPermissionChecker:
    """Implémentation Supabase de ILogoPermissionChecker (user_company_accesses)."""

    def can_edit_entity_logo(
        self,
        user_id: str,
        is_super_admin: bool,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """
        Retourne True si l'utilisateur peut modifier le logo de l'entité.
        company : admin ou rh de cette company (user_company_accesses), ou super_admin.
        group : super_admin uniquement.
        """
        if entity_type == "company":
            if is_super_admin:
                return True
            access = (
                supabase.table("user_company_accesses")
                .select("role")
                .eq("user_id", user_id)
                .eq("company_id", entity_id)
                .execute()
            )
            if not access.data or len(access.data) == 0:
                return False
            return access.data[0].get("role") in ["admin", "rh"]

        if entity_type == "group":
            return is_super_admin

        return False


_default_checker: ILogoPermissionChecker = LogoPermissionChecker()


def can_edit_entity_logo(
    user_id: str,
    is_super_admin: bool,
    entity_type: str,
    entity_id: str,
) -> bool:
    """
    Retourne True si l'utilisateur peut modifier le logo de l'entité.
    company : admin ou rh de cette company (user_company_accesses), ou super_admin.
    group : super_admin uniquement.
    """
    return _default_checker.can_edit_entity_logo(
        user_id=user_id,
        is_super_admin=is_super_admin,
        entity_type=entity_type,
        entity_id=entity_id,
    )
