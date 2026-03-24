"""
Router du module super_admin.

Délègue toute la logique à la couche application (queries, commands, service).
Aucune logique métier dans le router ; comportement HTTP identique au legacy.
Module autonome : ne dépend pas de app.modules.users ni app.modules.companies.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.security import get_current_user

from app.modules.super_admin.application import commands, queries
from app.modules.super_admin.application.service import (
    SuperAdminAccessError,
    verify_super_admin_and_return_row,
)
from app.modules.super_admin.application import tests as tests_app
from app.modules.super_admin.schemas.requests import (
    CompanyCreateWithAdmin,
    CompanyUpdate,
    ReductionFillonRequest,
    RunTestsRequest,
    UserCreate,
)

router = APIRouter(prefix="/api/super-admin", tags=["Super Admin"])


# ----- Dépendance : vérifier super admin -----


class _CurrentUserProtocol(Protocol):
    """Contrat minimal pour l'utilisateur courant (évite dépendance à app.modules.users)."""
    id: Any  # str ou UUID selon get_current_user


async def verify_super_admin(
    current_user: _CurrentUserProtocol = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retourne la ligne super_admins (dict) ou lève HTTP 403."""
    try:
        return verify_super_admin_and_return_row(str(current_user.id))
    except SuperAdminAccessError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Erreur lors de la vérification : {str(e)}",
        ) from e


def _map_exceptions(e: Exception) -> HTTPException:
    """Mappe les exceptions métier vers HTTP."""
    if isinstance(e, SuperAdminAccessError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, RuntimeError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erreur : {str(e)}",
    )


# ----- Dashboard & statistiques -----


@router.get("/dashboard/stats")
async def get_global_stats(
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Récupère les statistiques globales de toute la plateforme."""
    try:
        return queries.get_global_stats(super_admin)
    except Exception as e:
        raise _map_exceptions(e)


# ----- Companies -----


@router.get("/companies")
async def list_companies(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Liste toutes les entreprises avec filtres."""
    try:
        return queries.list_companies(
            skip=skip, limit=limit, search=search, is_active=is_active
        )
    except Exception as e:
        raise _map_exceptions(e)


@router.get("/companies/{company_id}")
async def get_company_details(
    company_id: str,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Récupère les détails d'une entreprise."""
    try:
        return queries.get_company_details(company_id)
    except Exception as e:
        raise _map_exceptions(e)


@router.post("/companies")
async def create_company(
    company: CompanyCreateWithAdmin,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Crée une nouvelle entreprise avec son administrateur."""
    try:
        return commands.create_company_with_admin(
            company.model_dump(), super_admin
        )
    except Exception as e:
        raise _map_exceptions(e)


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: str,
    company_update: CompanyUpdate,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Met à jour une entreprise."""
    try:
        update_data = {
            k: v
            for k, v in company_update.model_dump().items()
            if v is not None
        }
        return commands.update_company(company_id, update_data)
    except Exception as e:
        raise _map_exceptions(e)


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: str,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Désactive une entreprise (soft delete)."""
    try:
        return commands.delete_company_soft(company_id, super_admin)
    except Exception as e:
        raise _map_exceptions(e)


@router.delete("/companies/{company_id}/permanent")
async def delete_company_permanent(
    company_id: str,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Supprime définitivement une entreprise et toutes ses données."""
    try:
        return commands.delete_company_permanent(company_id, super_admin)
    except Exception as e:
        raise _map_exceptions(e)


# ----- Users (global) -----


@router.get("/users")
async def list_all_users(
    skip: int = 0,
    limit: int = 50,
    company_id: Optional[str] = None,
    role: Optional[str] = None,
    search: Optional[str] = None,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Liste tous les utilisateurs de toutes les entreprises."""
    try:
        return queries.list_all_users(
            skip=skip,
            limit=limit,
            company_id=company_id,
            role=role,
            search=search,
        )
    except Exception as e:
        raise _map_exceptions(e)


# ----- Users par entreprise -----


@router.get("/companies/{company_id}/users")
async def get_company_users(
    company_id: str,
    role: Optional[str] = None,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Récupère tous les utilisateurs ayant accès à une entreprise."""
    try:
        return queries.get_company_users(company_id, role=role)
    except Exception as e:
        raise _map_exceptions(e)


@router.post("/companies/{company_id}/users")
async def create_company_user(
    company_id: str,
    user_data: UserCreate,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Crée un nouvel utilisateur pour une entreprise."""
    try:
        return commands.create_company_user(
            company_id, user_data.model_dump()
        )
    except Exception as e:
        raise _map_exceptions(e)


@router.patch("/companies/{company_id}/users/{user_id}")
async def update_company_user(
    company_id: str,
    user_id: str,
    update_data: Dict[str, Any] = Body(...),
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Met à jour les informations d'un utilisateur."""
    try:
        return commands.update_company_user(
            company_id, user_id, update_data
        )
    except Exception as e:
        raise _map_exceptions(e)


@router.delete("/companies/{company_id}/users/{user_id}")
async def delete_company_user(
    company_id: str,
    user_id: str,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Supprime un utilisateur d'une entreprise (ou complètement si plus d'accès)."""
    try:
        return commands.delete_company_user(company_id, user_id)
    except Exception as e:
        raise _map_exceptions(e)


# ----- Monitoring -----


@router.get("/system/health")
async def get_system_health(
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Récupère l'état de santé du système."""
    try:
        return queries.get_system_health()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----- Tests (pytest backend_api/tests + Playwright e2e/) -----


@router.get("/tests/tree")
async def get_tests_tree(
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Arbre des cibles : pytest (``backend_api/tests``) + Playwright (``e2e/``) si le dossier existe."""
    return tests_app.get_tests_tree()


@router.post("/tests/run")
async def run_tests(
    body: RunTestsRequest = Body(...),
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Exécute pytest (chemins sous ``backend_api``) ou Playwright (cibles préfixées ``pw:``)."""
    return tests_app.run_tests(body.targets)


@router.get("/super-admins")
async def list_super_admins(
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Liste tous les super administrateurs."""
    try:
        return queries.list_super_admins()
    except Exception as e:
        raise _map_exceptions(e)


# ----- Réduction Fillon -----


@router.post("/reduction-fillon/calculate")
async def calculate_reduction_fillon(
    request: ReductionFillonRequest,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Calcule la réduction Fillon pour un employé et un mois donnés."""
    try:
        return queries.calculate_reduction_fillon(
            request.employee_id, request.month, request.year
        )
    except Exception as e:
        raise _map_exceptions(e)


@router.get("/reduction-fillon/employees")
async def get_employees_for_reduction_fillon(
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
):
    """Récupère la liste des employés pour le test réduction Fillon."""
    try:
        return queries.get_employees_for_reduction_fillon()
    except Exception as e:
        raise _map_exceptions(e)
