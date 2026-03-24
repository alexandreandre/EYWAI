"""
Cas d'usage écriture / effets de bord pour access_control.

Logique applicative extraite des routers legacy : require_rh_access, quick_create_role_template.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from app.modules.access_control.application.service import access_control_service
from app.modules.access_control.infrastructure.queries import role_template_repository

if TYPE_CHECKING:
    from app.modules.users.schemas.responses import User


def require_rh_access(current_user: "User") -> None:
    """
    Lève HTTPException 403 si l'utilisateur n'a aucun accès RH.
    Wrapper vers le service ; à utiliser en Depends(require_rh_access) dans l'API.
    """
    access_control_service.require_rh_access(current_user)


def require_rh_access_for_company(
    current_user: "User", company_id: str
) -> None:
    """
    Lève HTTPException 403 si l'utilisateur n'a pas d'accès RH pour cette entreprise.
    Aligné legacy GET /check-permission (garder même comportement que user_management).
    """
    access_control_service.require_rh_access_for_company(
        current_user, company_id
    )


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
    if not current_user.is_super_admin:
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
