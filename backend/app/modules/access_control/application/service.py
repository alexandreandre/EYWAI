"""
Service d'autorisation : centralise les vérifications de permissions et de hiérarchie des rôles.

Le router du module (app/modules/access_control/api/router.py) utilise ce service.
Les routers legacy (api/routers/user_management, user_creation, users, employee_exits)
conservent leurs définitions locales ou importent depuis user_management ; ne pas
supprimer ces imports tant que les clients n'ont pas basculé vers /api/access-control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.modules.access_control.domain import rules
from app.modules.access_control.domain.interfaces import IPermissionRepository
from app.modules.access_control.infrastructure.repository import (
    SupabasePermissionRepository,
)

if TYPE_CHECKING:
    from uuid import UUID

    from app.modules.users.schemas.responses import User

# Instance par défaut (utilise Supabase). Peut être remplacée par une injection pour les tests.
_default_repository: IPermissionRepository = SupabasePermissionRepository()


def get_access_control_service(
    permission_repository: IPermissionRepository | None = None,
) -> "AccessControlService":
    """Retourne le service d'accès, avec repository optionnel (pour tests)."""
    return AccessControlService(permission_repository or _default_repository)


class AccessControlService:
    """Helpers d'autorisation métier : hiérarchie rôles, permissions, accès RH."""

    def __init__(self, permission_repository: IPermissionRepository):
        self._perms = permission_repository

    def check_role_hierarchy_access(
        self,
        creator_user: "User",
        target_role: str,
        company_id: str | "UUID",
    ) -> bool:
        """
        Vérifie si l'utilisateur créateur peut créer/modifier un utilisateur
        avec le rôle cible dans l'entreprise donnée.
        """
        if creator_user.is_super_admin:
            return True
        creator_role = creator_user.get_role_in_company(str(company_id))
        if not creator_role:
            return False
        return rules.can_assign_role(creator_role, target_role)

    def check_user_has_permission(
        self,
        user_id: str,
        company_id: str,
        permission_code: str,
    ) -> bool:
        """Vérifie si un utilisateur possède une permission spécifique dans l'entreprise."""
        return self._perms.user_has_permission(user_id, company_id, permission_code)

    def has_any_rh_permission(self, user_id: str, company_id: str) -> bool:
        """
        Vérifie si un utilisateur (rôle custom) a au moins une permission
        dont required_role in ('rh', 'admin').
        """
        return self._perms.user_has_any_rh_permission(user_id, company_id)

    def get_viewable_roles(self, creator_role: str) -> list[str]:
        """Liste des rôles dont le créateur peut voir les permissions (ex. pour GET user permissions)."""
        return rules.get_viewable_roles(creator_role)

    def require_rh_access(self, current_user: "User") -> None:
        """
        Lève HTTPException 403 si l'utilisateur n'a aucun accès RH
        (super_admin ou has_rh_access_in_company sur au moins une entreprise).
        """
        if current_user.is_super_admin:
            return
        has_rh = any(
            current_user.has_rh_access_in_company(acc.company_id)
            for acc in current_user.accessible_companies
        )
        if not has_rh:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès RH requis",
            )

    def require_rh_access_for_company(
        self, current_user: "User", company_id: str
    ) -> None:
        """
        Lève HTTPException 403 si l'utilisateur n'a pas d'accès RH pour cette entreprise.
        Aligné legacy check-permission : super_admin ou has_rh_access_in_company(company_id).
        """
        if current_user.is_super_admin:
            return
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès RH requis",
            )

    def can_access_company_as_rh(self, current_user: "User", company_id: str) -> bool:
        """
        True si l'utilisateur a accès RH pour cette entreprise (pour ex. matrice des permissions).
        Règle pure pour admin/rh/collaborateur_rh ; custom nécessite la persistance (repository).
        """
        if current_user.is_super_admin:
            return True
        role = current_user.get_role_in_company(company_id)
        if rules.role_has_rh_level(role or ""):
            return True
        if role == "custom":
            return self.has_any_rh_permission(str(current_user.id), company_id)
        return False


# Singleton pour usage dans les routers après migration.
access_control_service = get_access_control_service()
