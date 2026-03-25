"""
Cas d'usage lecture pour access_control.

Logique applicative extraite des routers legacy (user_management) : listes catégories,
actions, permissions, matrice, résumé permissions utilisateur, templates de rôles.
Les vérifications RH / hiérarchie sont déléguées au service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from fastapi import HTTPException, status

from app.modules.access_control.application.dto import (
    PermissionCheckResult,
    RoleHierarchyCheckResult,
)
from app.modules.access_control.application.service import access_control_service
from app.modules.access_control.infrastructure.queries import (
    permission_catalog_reader,
    role_template_repository,
)

if TYPE_CHECKING:
    from app.modules.users.schemas.responses import User


# --- Vérifications pures (déjà utilisées par le router du module) ---


def check_hierarchy(
    current_user: "User",
    target_role: str,
    company_id: str,
) -> RoleHierarchyCheckResult:
    """
    Vérifie si l'utilisateur courant peut créer/modifier un utilisateur avec le rôle cible.
    Délègue au service.
    """
    is_allowed = access_control_service.check_role_hierarchy_access(
        current_user, target_role, company_id
    )
    creator_role = (
        current_user.get_role_in_company(company_id)
        if not current_user.is_super_admin
        else "super_admin"
    )
    return RoleHierarchyCheckResult(
        is_allowed=is_allowed,
        creator_role=creator_role or "none",
        target_role=target_role,
        company_id=company_id,
    )


def check_permission(
    user_id: str,
    company_id: str,
    permission_code: str,
) -> PermissionCheckResult:
    """
    Vérifie si un utilisateur possède une permission donnée dans l'entreprise.
    Délègue au service (repository).
    """
    has_permission = access_control_service.check_user_has_permission(
        user_id, company_id, permission_code
    )
    return PermissionCheckResult(
        has_permission=has_permission,
        permission_code=permission_code,
        user_id=user_id,
        company_id=company_id,
    )


# --- Listes (catégories, actions, permissions) ---


def get_permission_categories(current_user: "User") -> list:
    """
    Liste toutes les catégories de permissions actives.
    L'appelant doit avoir vérifié l'accès RH (require_rh_access) avant d'appeler.
    """
    from app.modules.access_control.schemas import PermissionCategory

    rows = permission_catalog_reader.get_permission_categories_active()
    return [PermissionCategory(**row) for row in rows]


def get_permission_actions(current_user: "User") -> list:
    """
    Liste toutes les actions de permissions actives.
    L'appelant doit avoir vérifié l'accès RH avant d'appeler.
    """
    from app.modules.access_control.schemas import PermissionAction

    rows = permission_catalog_reader.get_permission_actions_active()
    return [PermissionAction(**row) for row in rows]


def get_all_permissions(
    current_user: "User",
    category_id: Optional[str] = None,
    required_role: Optional[str] = None,
) -> list:
    """
    Liste toutes les permissions actives avec filtres optionnels.
    L'appelant doit avoir vérifié l'accès RH avant d'appeler.
    """
    from app.modules.access_control.schemas import Permission

    rows = permission_catalog_reader.get_permissions_active(
        category_id=category_id,
        required_role=required_role,
    )
    return [Permission(**row) for row in rows]


# --- Matrice des permissions ---


def get_permissions_matrix(
    current_user: "User",
    company_id: str,
    user_id: Optional[str] = None,
) -> "object":
    """
    Matrice des permissions par catégorie pour une entreprise.
    Si user_id fourni : permissions accordées à cet utilisateur ; sinon à current_user.
    Lève 403 si l'utilisateur n'a pas accès RH pour cette entreprise.
    """
    from app.modules.access_control.schemas import (
        PermissionMatrix,
        PermissionMatrixCategory,
    )

    if not access_control_service.can_access_company_as_rh(current_user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès RH requis pour cette entreprise",
        )

    categories = permission_catalog_reader.get_permission_categories_active()
    all_permissions = permission_catalog_reader.get_permissions_for_matrix()
    actions = permission_catalog_reader.get_permission_actions_active()
    actions_map = {a["id"]: a for a in actions}

    for perm in all_permissions:
        perm["permission_actions"] = actions_map.get(perm.get("action_id"))

    effective_user_id = user_id if user_id else current_user.id
    granted_ids = permission_catalog_reader.get_user_permission_ids(
        str(effective_user_id), company_id
    )

    matrix_data = []
    for category in categories:
        category_permissions = [
            {
                **perm,
                "is_granted": str(perm["id"]) in granted_ids,
                "action_code": (
                    perm["permission_actions"]["code"]
                    if perm.get("permission_actions")
                    else None
                ),
                "action_label": (
                    perm["permission_actions"]["label"]
                    if perm.get("permission_actions")
                    else None
                ),
            }
            for perm in all_permissions
            if perm.get("category_id") == category["id"]
        ]
        matrix_data.append(
            PermissionMatrixCategory(
                code=category["code"],
                label=category["label"],
                description=category.get("description"),
                actions=category_permissions,
            )
        )
    return PermissionMatrix(categories=matrix_data)


# --- Permissions d'un utilisateur (résumé) ---


def get_user_permissions_summary(
    current_user: "User",
    user_id: str,
    company_id: str,
) -> "object":
    """
    Résumé des permissions d'un utilisateur dans une entreprise.
    Respecte la hiérarchie : seuls les rôles visibles par le créateur sont autorisés.
    Lève 403 si accès RH manquant ou utilisateur cible hors hiérarchie.
    """
    from app.modules.access_control.schemas import (
        UserPermissionsSummary,
        PermissionWithMetadata,
    )

    access = permission_catalog_reader.get_user_company_access(user_id, company_id)
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur n'a pas d'accès à cette entreprise",
        )
    target_user_role = access["role"]

    if not current_user.is_super_admin:
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès RH requis",
            )
        viewable_roles = access_control_service.get_viewable_roles(
            current_user.get_role_in_company(company_id) or ""
        )
        if target_user_role not in viewable_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas autorisé à voir les permissions de cet utilisateur",
            )

    user_perm_ids = list(
        permission_catalog_reader.get_user_permission_ids(user_id, company_id)
    )
    if not user_perm_ids:
        permissions_list = []
        permissions_by_category = {}
    else:
        perms_details = permission_catalog_reader.get_permissions_details_by_ids(
            user_perm_ids
        )
        permissions_list = []
        permissions_by_category = {}
        for perm in perms_details:
            cat = perm.get("permission_categories") or {}
            action = perm.get("permission_actions") or {}
            permissions_list.append(
                PermissionWithMetadata(
                    id=perm["id"],
                    code=perm["code"],
                    label=perm["label"],
                    description=perm.get("description"),
                    category_code=cat.get("code"),
                    category_label=cat.get("label"),
                    action_code=action.get("code"),
                    action_label=action.get("label"),
                    required_role=perm.get("required_role"),
                    is_active=perm.get("is_active", True),
                    is_granted=True,
                )
            )
            cat_code = cat.get("code")
            if cat_code:
                permissions_by_category[cat_code] = (
                    permissions_by_category.get(cat_code, 0) + 1
                )

    role_templates = access.get("role_templates") or {}
    template_name = (
        role_templates.get("name") if isinstance(role_templates, dict) else None
    )

    return UserPermissionsSummary(
        user_id=user_id,
        company_id=company_id,
        base_role=access["role"],
        role_template_id=access.get("role_template_id"),
        role_template_name=template_name,
        total_permissions=len(permissions_list),
        permissions_by_category=permissions_by_category,
        all_permissions=permissions_list,
    )


# --- Templates de rôles ---


def get_role_templates(
    current_user: "User",
    company_id: Optional[str] = None,
    base_role: Optional[str] = None,
    include_system: bool = True,
) -> List["object"]:
    """
    Liste les templates de rôles (avec comptage des permissions).
    L'appelant doit avoir vérifié l'accès RH avant d'appeler.
    """
    from app.modules.access_control.schemas import RoleTemplateDetail

    templates = role_template_repository.get_role_templates_list(
        company_id=company_id,
        base_role=base_role,
        include_system=include_system,
    )
    result = []
    for template in templates:
        count = role_template_repository.get_role_template_permissions_count(
            template["id"]
        )
        result.append(
            RoleTemplateDetail(
                id=template["id"],
                name=template["name"],
                description=template.get("description"),
                job_title=template.get("job_title"),
                base_role=template["base_role"],
                is_system=template.get("is_system", False),
                is_active=template.get("is_active", True),
                company_id=template.get("company_id"),
                company_name=None,
                created_by=template.get("created_by"),
                created_by_name=None,
                created_at=template["created_at"],
                updated_at=template["updated_at"],
                permissions_count=count,
                permissions=[],
            )
        )
    return result


def get_role_template_by_id(current_user: "User", template_id: str) -> "object":
    """
    Un template de rôle avec ses permissions.
    L'appelant doit avoir vérifié l'accès RH avant d'appeler.
    """
    from app.modules.access_control.schemas import (
        Permission,
        RoleTemplateWithPermissions,
    )

    template = role_template_repository.get_role_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template non trouvé",
        )
    perms_rows = role_template_repository.get_role_template_permission_details(
        template_id
    )
    permissions_list = [Permission(**p) for p in perms_rows]
    return RoleTemplateWithPermissions(
        **template,
        permissions=permissions_list,
        permissions_count=len(permissions_list),
    )
