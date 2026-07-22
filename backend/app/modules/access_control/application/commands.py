"""
Cas d'usage écriture / effets de bord pour access_control.

Logique applicative extraite des routers legacy : require_rh_access, quick_create_role_template.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from app.modules.access_control.application.service import access_control_service
from app.modules.access_control.infrastructure.queries import (
    permission_catalog_reader,
    role_template_repository,
)

if TYPE_CHECKING:
    from app.modules.users.schemas.responses import User


def require_rh_access(current_user: "User") -> None:
    """
    Lève HTTPException 403 si l'utilisateur n'a aucun accès RH.
    Wrapper vers le service ; à utiliser en Depends(require_rh_access) dans l'API.
    """
    access_control_service.require_rh_access(current_user)


def require_rh_access_for_company(current_user: "User", company_id: str) -> None:
    """
    Lève HTTPException 403 si l'utilisateur n'a pas d'accès RH pour cette entreprise.
    Aligné legacy GET /check-permission (garder même comportement que user_management).
    """
    access_control_service.require_rh_access_for_company(current_user, company_id)


def quick_create_role_template(
    current_user: "User",
    name: str,
    job_title: str,
    base_role: str,
    company_id: str,
    description: str | None = None,
    permission_ids: list | None = None,
) -> dict[str, Any]:
    """
    Crée un template de rôle pour une entreprise et associe les permissions.
    Lève 403 si pas d'accès RH pour l'entreprise, 400 si le nom existe déjà.
    Retourne {"message": "...", "template_id": "...", "name": "..."}.
    """
    if not current_user.is_platform_admin:
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès RH requis pour cette entreprise",
            )

    if role_template_repository.role_template_name_exists(company_id, name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Un template avec le nom '{name}' existe déjà pour cette entreprise",
        )

    template_id = role_template_repository.create_role_template(
        company_id=company_id,
        name=name,
        description=description,
        job_title=job_title,
        base_role=base_role,
        created_by=str(current_user.id),
    )

    if permission_ids:
        role_template_repository.attach_permissions_to_role_template(
            template_id, permission_ids
        )

    return {
        "message": "Template créé avec succès",
        "template_id": template_id,
        "name": name,
    }


def _assert_can_manage_user_permissions(
    current_user: "User", user_id: str, company_id: str
) -> None:
    """Vérifie que l'appelant peut modifier les permissions de l'utilisateur cible."""
    access = permission_catalog_reader.get_user_company_access(user_id, company_id)
    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur n'a pas d'accès à cette entreprise",
        )
    target_user_role = access["role"]
    if not current_user.is_platform_admin:
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
                detail="Vous n'êtes pas autorisé à modifier les permissions de cet utilisateur",
            )


def replace_user_permissions(
    current_user: "User",
    user_id: str,
    company_id: str,
    permission_ids: list | None,
    grants: list | None = None,
) -> dict[str, str]:
    """
    Remplace toutes les permissions utilisateur pour une entreprise (PUT).

    Si `grants` est fourni, remplacement atomique permissions + scopes.
    Sinon, comportement legacy : permission_ids (scope company par défaut en DB).
    """
    from app.modules.users.infrastructure.repository import user_permission_repository

    _assert_can_manage_user_permissions(current_user, user_id, company_id)
    grantor = str(current_user.id)

    if grants is not None:
        from app.modules.access_control.infrastructure.scoped_repository import (
            scoped_permission_repository,
        )

        payload: list[dict[str, Any]] = []
        for g in grants:
            if hasattr(g, "model_dump"):
                raw = g.model_dump()
            else:
                raw = dict(g)
            payload.append(
                {
                    "permission_id": str(raw["permission_id"]),
                    "scope_mode": raw.get("scope_mode") or "company",
                    "team_ids": [str(t) for t in (raw.get("team_ids") or [])],
                    "targets": [
                        {
                            "employee_id": str(t["employee_id"]),
                            "effect": t["effect"],
                        }
                        for t in (raw.get("targets") or [])
                    ],
                }
            )
        scoped_permission_repository.replace_grants_atomic(
            user_id=user_id,
            company_id=company_id,
            granted_by=grantor,
            grants=payload,
        )
        return {"message": "Permissions et périmètres mis à jour"}

    ids = [str(p) for p in (permission_ids or [])]
    user_permission_repository.delete_for_user_company(user_id, company_id)
    for permission_id in ids:
        user_permission_repository.upsert(
            user_id, company_id, permission_id, grantor
        )
    return {"message": "Permissions mises à jour"}


def grant_user_permissions(
    current_user: "User",
    user_id: str,
    company_id: str,
    permission_ids: list | None,
) -> dict[str, str]:
    """Ajoute des permissions sans supprimer les existantes (POST) — scope company."""
    from app.modules.users.infrastructure.repository import user_permission_repository

    _assert_can_manage_user_permissions(current_user, user_id, company_id)
    grantor = str(current_user.id)
    for permission_id in [str(p) for p in (permission_ids or [])]:
        user_permission_repository.upsert(
            user_id, company_id, permission_id, grantor
        )
    return {"message": "Permissions accordées"}


def get_user_permission_grants(
    current_user: "User", user_id: str, company_id: str
) -> list[dict[str, Any]]:
    """Liste détaillée des grants + scopes pour l'éditeur UI."""
    _assert_can_manage_user_permissions(current_user, user_id, company_id)
    from app.modules.access_control.infrastructure.scoped_repository import (
        scoped_permission_repository,
    )

    return scoped_permission_repository.list_grants_for_user_company(
        user_id, company_id
    )