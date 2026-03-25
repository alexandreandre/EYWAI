"""
Router du module users.

Délègue toute la logique à l'application (commands, queries, service).
Contrat HTTP identique aux anciens api/routers/users.py et user_creation.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.users.application import commands, queries
from app.modules.users.application.service import (
    check_role_hierarchy,
    has_any_rh_permission,
)
from app.modules.users.schemas.requests import (
    SetPrimaryCompanyRequest,
    UserCompanyAccessCreate,
    UserCompanyAccessCreateByUserId,
    UserCompanyAccessUpdate,
    UserCreateWithPermissions,
    UserUpdateWithPermissions,
)
from app.modules.users.schemas.responses import CompanyAccess, User, UserDetail

from app.core.security import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


def _handle_application_errors(e: Exception) -> None:
    """Traduit les exceptions applicatives en HTTPException."""
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erreur inattendue: {str(e)}",
    )


# ----- Routes ex-users.py -----


@router.get("/my-companies", response_model=List[CompanyAccess])
async def get_my_companies(current_user: User = Depends(get_current_user)):
    """Entreprises accessibles (super_admin: toutes actives, sinon accessible_companies)."""
    try:
        return queries.get_my_companies(current_user)
    except Exception as e:
        _handle_application_errors(e)


@router.get("/me", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Profil complet de l'utilisateur connecté."""
    return queries.get_me(current_user)


@router.patch("/set-primary-company")
async def set_primary_company(
    request: SetPrimaryCompanyRequest,
    current_user: User = Depends(get_current_user),
):
    """Définit l'entreprise primaire. Vérification d'accès côté router."""
    if not current_user.has_access_to_company(request.company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Vous n'avez pas accès à l'entreprise {request.company_id}",
        )
    try:
        result = commands.set_primary_company(
            current_user.id, request.company_id, current_user
        )
        return {"message": result.message, "company_id": result.company_id}
    except Exception as e:
        _handle_application_errors(e)


@router.get("/company-accesses/{user_id}", response_model=List[CompanyAccess])
async def get_user_company_accesses(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """Accès entreprises d'un utilisateur (super_admin ou admin d'une entreprise commune)."""
    try:
        return queries.get_user_company_accesses(user_id, current_user)
    except Exception as e:
        _handle_application_errors(e)


@router.post("/grant-access")
async def grant_company_access(
    request: UserCompanyAccessCreate,
    current_user: User = Depends(get_current_user),
):
    """Accorde l'accès à une entreprise (par email). Vérification RH côté router."""
    if not current_user.is_super_admin:
        has_rh = current_user.has_rh_access_in_company(request.company_id)
        if not has_rh and not has_any_rh_permission(
            str(current_user.id), request.company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez avoir un accès RH dans l'entreprise pour accorder des accès",
            )
    try:
        result = commands.grant_company_access_by_email(
            request.user_email,
            request.company_id,
            request.role,
            request.is_primary,
            current_user,
        )
        return {"message": result.message, "access": result.access}
    except Exception as e:
        _handle_application_errors(e)


@router.post("/grant-access-by-user-id")
async def grant_company_access_by_user_id(
    request: UserCompanyAccessCreateByUserId,
    current_user: User = Depends(get_current_user),
):
    """Accorde l'accès à une entreprise (par user_id). Vérification RH côté router."""
    if not current_user.is_super_admin:
        has_rh = current_user.has_rh_access_in_company(request.company_id)
        if not has_rh and not has_any_rh_permission(
            str(current_user.id), request.company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez avoir un accès RH dans l'entreprise pour accorder des accès",
            )
    try:
        result = commands.grant_company_access_by_user_id(
            request.user_id,
            request.company_id,
            request.role,
            request.is_primary,
            current_user,
        )
        return {"message": result.message, "access": result.access}
    except Exception as e:
        _handle_application_errors(e)


@router.delete("/revoke-access/{user_id}/{company_id}")
async def revoke_company_access(
    user_id: str,
    company_id: str,
    current_user: User = Depends(get_current_user),
):
    """Révoque l'accès. Réservé aux admins de l'entreprise ou super_admin."""
    if not current_user.is_super_admin:
        if not current_user.is_admin_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez être admin de l'entreprise pour révoquer des accès",
            )
    try:
        result = commands.revoke_company_access(user_id, company_id, current_user)
        return {
            "message": result.message,
            "user_id": result.user_id,
            "company_id": result.company_id,
        }
    except Exception as e:
        _handle_application_errors(e)


@router.patch("/update-access/{user_id}/{company_id}")
async def update_company_access(
    user_id: str,
    company_id: str,
    request: UserCompanyAccessUpdate,
    current_user: User = Depends(get_current_user),
):
    """Modifie l'accès (rôle ou is_primary). Réservé aux admins ou super_admin."""
    if not current_user.is_super_admin:
        if not current_user.is_admin_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez être admin de l'entreprise pour modifier des accès",
            )
    try:
        result = commands.update_company_access(
            user_id,
            company_id,
            request.role,
            request.is_primary,
            current_user,
        )
        return {"message": result.message, "access": result.access}
    except Exception as e:
        _handle_application_errors(e)


# ----- Routes ex-user_creation.py -----


@router.post("/create-with-permissions", status_code=status.HTTP_201_CREATED)
async def create_user_with_permissions(
    data: UserCreateWithPermissions,
    current_user: User = Depends(get_current_user),
):
    """Crée un utilisateur avec permissions. Vérifications primaire + hiérarchie côté router."""
    primary_count = sum(1 for a in data.company_accesses if a.is_primary)
    if primary_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Au moins un accès doit être marqué comme primaire",
        )
    if primary_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un seul accès peut être marqué comme primaire",
        )
    if not current_user.is_super_admin:
        for access in data.company_accesses:
            if not current_user.has_access_to_company(str(access.company_id)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Vous n'avez pas accès à l'entreprise {access.company_id}",
                )
            if not check_role_hierarchy(
                current_user, access.base_role, str(access.company_id)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Vous ne pouvez pas créer d'utilisateurs avec le rôle '{access.base_role}' dans cette entreprise",
                )
    try:
        result = commands.create_user_with_permissions(data, current_user)
        return {
            "message": result.message,
            "user_id": result.user_id,
            "email": result.email,
            "companies_count": result.companies_count,
        }
    except Exception as e:
        _handle_application_errors(e)


@router.get("/company/{company_id}", response_model=List[UserDetail])
async def get_company_users(
    company_id: str,
    role: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Liste les utilisateurs d'une entreprise (RH/Admin)."""
    if not current_user.is_super_admin:
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès RH requis pour cette entreprise",
            )
    try:
        return queries.get_company_users(company_id, role, current_user)
    except Exception as e:
        _handle_application_errors(e)


@router.get("/accessible-companies")
async def get_accessible_companies_for_user_creation(
    current_user: User = Depends(get_current_user),
):
    """Entreprises dans lesquelles l'utilisateur peut créer des utilisateurs + rôles créables."""
    try:
        return queries.get_accessible_companies_for_user_creation(current_user)
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{user_id}")
async def get_user_detail(
    user_id: str,
    company_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'un utilisateur pour une entreprise (profil, rôle, permissions, can_edit)."""
    try:
        return queries.get_user_detail(user_id, company_id, current_user)
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{user_id}/update")
async def update_user_with_permissions(
    user_id: str,
    data: UserUpdateWithPermissions,
    current_user: User = Depends(get_current_user),
):
    """Modifie un utilisateur (profil, rôle, permissions). Vérification hiérarchie côté router."""
    company_id = str(data.company_id)
    if not current_user.is_super_admin:
        if not current_user.has_access_to_company(company_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Vous n'avez pas accès à l'entreprise {company_id}",
            )
        # Vérification editable + rôle cible faite dans l'application (get_user_detail / update)
        # On s'appuie sur la commande qui lève si non modifiable
    try:
        result = commands.update_user_with_permissions(user_id, data, current_user)
        return {"message": result.message, "user_id": result.user_id}
    except Exception as e:
        _handle_application_errors(e)
