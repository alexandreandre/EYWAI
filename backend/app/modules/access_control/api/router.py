"""
Router du module access_control.

Délègue toute la logique à la couche application (queries, commands).
Aucune logique métier lourde ni accès DB direct. Comportement HTTP identique au legacy.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, status

from app.core.security import get_current_user
from app.modules.access_control.application import commands, queries
from app.modules.access_control.schemas import (
    Permission,
    PermissionAction,
    PermissionCategory,
    PermissionCheckResponse,
    PermissionMatrix,
    RoleHierarchyCheckResponse,
    RoleTemplateDetail,
    RoleTemplateQuickCreate,
    RoleTemplateWithPermissions,
    UserPermissionsSummary,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/access-control", tags=["Access Control"])


def _require_rh_access(current_user: User = Depends(get_current_user)) -> User:
    """Dépendance : lève 403 si pas d'accès RH. Sinon retourne current_user."""
    commands.require_rh_access(current_user)
    return current_user


# --- Catégories / actions / permissions ---

@router.get("/permission-categories", response_model=List[PermissionCategory])
async def get_permission_categories(
    current_user: User = Depends(_require_rh_access),
):
    """Liste toutes les catégories de permissions actives."""
    return queries.get_permission_categories(current_user)


@router.get("/permission-actions", response_model=List[PermissionAction])
async def get_permission_actions(
    current_user: User = Depends(_require_rh_access),
):
    """Liste toutes les actions de permissions actives."""
    return queries.get_permission_actions(current_user)


@router.get("/permissions", response_model=List[Permission])
async def get_all_permissions(
    category_id: Optional[str] = None,
    required_role: Optional[str] = None,
    current_user: User = Depends(_require_rh_access),
):
    """Liste toutes les permissions actives (filtres optionnels)."""
    return queries.get_all_permissions(
        current_user,
        category_id=category_id,
        required_role=required_role,
    )


@router.get("/permissions/matrix", response_model=PermissionMatrix)
async def get_permissions_matrix(
    company_id: str,
    user_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Matrice des permissions par catégorie pour une entreprise. Vérification RH côté application."""
    return queries.get_permissions_matrix(
        current_user, company_id, user_id=user_id
    )


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsSummary)
async def get_user_permissions(
    user_id: str,
    company_id: str,
    current_user: User = Depends(get_current_user),
):
    """Résumé des permissions d'un utilisateur dans une entreprise. Hiérarchie et RH gérés par l'application."""
    return queries.get_user_permissions_summary(
        current_user, user_id, company_id
    )


# --- Templates de rôles ---

@router.get("/role-templates", response_model=List[RoleTemplateDetail])
async def get_role_templates(
    company_id: Optional[str] = None,
    base_role: Optional[str] = None,
    include_system: bool = True,
    current_user: User = Depends(_require_rh_access),
):
    """Liste les templates de rôles disponibles."""
    return queries.get_role_templates(
        current_user,
        company_id=company_id,
        base_role=base_role,
        include_system=include_system,
    )


@router.post("/role-templates/quick-create", status_code=status.HTTP_201_CREATED)
async def quick_create_role_template(
    data: RoleTemplateQuickCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée un template de rôle pour une entreprise. Vérification RH côté command."""
    return commands.quick_create_role_template(
        current_user,
        name=data.name,
        job_title=data.job_title,
        base_role=data.base_role,
        company_id=str(data.company_id),
        description=data.description,
        permission_ids=data.permission_ids or [],
    )


@router.get("/role-templates/{template_id}", response_model=RoleTemplateWithPermissions)
async def get_role_template(
    template_id: str,
    current_user: User = Depends(_require_rh_access),
):
    """Détail d'un template de rôle avec ses permissions."""
    return queries.get_role_template_by_id(current_user, template_id)


# --- Vérifications hiérarchie / permission (comportement legacy strict) ---

@router.get("/check-hierarchy", response_model=RoleHierarchyCheckResponse)
async def get_check_hierarchy(
    target_role: str,
    company_id: str,
    current_user: User = Depends(get_current_user),
):
    """Vérifie si l'utilisateur peut créer/modifier un utilisateur avec le rôle cible. Legacy : auth seule, pas de guard RH."""
    result = queries.check_hierarchy(current_user, target_role, company_id)
    if result.is_allowed:
        message = f"Vous pouvez créer/modifier des utilisateurs avec le rôle '{target_role}'"
    else:
        message = f"Vous ne pouvez pas créer/modifier des utilisateurs avec le rôle '{target_role}'"
    return RoleHierarchyCheckResponse(
        is_allowed=result.is_allowed,
        creator_role=result.creator_role,
        target_role=result.target_role,
        message=message,
    )


@router.get("/check-permission", response_model=PermissionCheckResponse)
async def get_check_permission(
    user_id: str,
    company_id: str,
    permission_code: str,
    current_user: User = Depends(get_current_user),
):
    """Vérifie si un utilisateur possède une permission donnée. Legacy : RH requis pour cette company_id."""
    commands.require_rh_access_for_company(current_user, company_id)
    result = queries.check_permission(user_id, company_id, permission_code)
    return PermissionCheckResponse(
        has_permission=result.has_permission,
        permission_code=result.permission_code,
        user_id=result.user_id,
        company_id=result.company_id,
    )
