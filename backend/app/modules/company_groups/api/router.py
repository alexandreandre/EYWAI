"""
Router API du module company_groups.

Délègue toute la logique à la couche application (queries, commands).
Vérifications d'autorisation minimales (super_admin, admin de X) puis appel application.
Comportement HTTP identique à api/routers/company_groups.py.
"""
from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.company_groups.api.auth import CurrentUserForCompanyGroups
from app.modules.company_groups.application import commands, queries
from app.modules.company_groups.application.service import (
    get_group_company_ids_for_permission_check,
)
from app.modules.company_groups.schemas.requests import (
    BulkAddCompaniesRequest,
    CompanyGroupCreate,
    ManageUserAccessRequest,
)
from app.modules.company_groups.schemas.responses import (
    CompanyGroup,
    CompanyInGroup,
    GroupWithCompanies,
)

router = APIRouter(prefix="/api/company-groups", tags=["company-groups"])


def _dto_to_group_with_companies(dto) -> GroupWithCompanies:
    """Construit GroupWithCompanies (response model) depuis GroupWithCompaniesDto."""
    companies = [
        CompanyInGroup(
            id=c["id"],
            company_name=c["company_name"],
            siret=c.get("siret"),
            is_active=c.get("is_active", True),
        )
        for c in dto.companies
    ]
    return GroupWithCompanies(
        id=dto.id,
        group_name=dto.group_name,
        siren=dto.siren,
        description=dto.description,
        logo_url=dto.logo_url,
        is_active=dto.is_active,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        companies=companies,
    )


def _handle_application_errors(e: Exception, default_message: str) -> None:
    """Traduit les exceptions applicatives en HTTPException."""
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=default_message)


# ----- GET : lecture -----

@router.get("/my-groups", response_model=List[GroupWithCompanies])
def get_my_groups(current_user: CurrentUserForCompanyGroups = Depends(get_current_user)):
    """Retourne tous les groupes d'entreprises auxquels l'utilisateur a accès."""
    try:
        dtos = queries.get_my_groups(current_user)
        return [_dto_to_group_with_companies(d) for d in dtos]
    except Exception as e:
        _handle_application_errors(e, "Erreur lors du chargement des groupes")


@router.get("/", response_model=List[dict])
def get_all_groups(current_user: CurrentUserForCompanyGroups = Depends(get_current_user)):
    """Liste tous les groupes avec statistiques (Super Admin uniquement)."""
    try:
        dtos = queries.get_all_groups(current_user)
        return [
            {
                "id": d.id,
                "group_name": d.group_name,
                "description": d.description,
                "created_at": d.created_at,
                "company_count": d.company_count,
                "total_employees": d.total_employees,
            }
            for d in dtos
        ]
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la récupération des groupes"
        )


@router.get("/{group_id}", response_model=GroupWithCompanies)
def get_group_details(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Retourne les détails d'un groupe et ses entreprises."""
    try:
        dto = queries.get_group_details(group_id, current_user)
        return _dto_to_group_with_companies(dto)
    except Exception as e:
        _handle_application_errors(e, "Erreur lors du chargement du groupe")


@router.get("/{group_id}/consolidated-stats")
def get_group_consolidated_stats(
    group_id: str,
    year: Optional[int] = Query(None, description="Année de référence"),
    month: Optional[int] = Query(None, description="Mois de référence"),
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Statistiques consolidées pour les entreprises du groupe."""
    try:
        return queries.get_group_consolidated_stats(
            group_id, current_user, year=year, month=month
        )
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors du calcul des statistiques"
        )


@router.get("/{group_id}/employees-stats")
def get_group_employees_stats(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Statistiques employés par entreprise du groupe."""
    try:
        return queries.get_group_employees_stats(group_id, current_user)
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors du calcul des statistiques employés"
        )


@router.get("/{group_id}/payroll-evolution")
def get_group_payroll_evolution(
    group_id: str,
    start_year: int = Query(..., description="Année de début"),
    start_month: int = Query(..., description="Mois de début (1-12)"),
    end_year: int = Query(..., description="Année de fin"),
    end_month: int = Query(..., description="Mois de fin (1-12)"),
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Évolution de la masse salariale mois par mois pour le groupe."""
    try:
        return queries.get_group_payroll_evolution(
            group_id,
            current_user,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
        )
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors du calcul de l'évolution"
        )


@router.get("/{group_id}/company-comparison")
def get_group_company_comparison(
    group_id: str,
    metric: str = Query(..., description="Métrique: employees, payroll, absences"),
    year: Optional[int] = Query(None, description="Année de référence"),
    month: Optional[int] = Query(None, description="Mois de référence"),
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Compare les entreprises du groupe sur une métrique."""
    try:
        return queries.get_group_company_comparison(
            group_id, current_user, metric=metric, year=year, month=month
        )
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la comparaison"
        )


@router.get("/{group_id}/companies")
def get_group_companies(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Liste les entreprises d'un groupe (Super Admin uniquement)."""
    try:
        return queries.get_group_companies(group_id, current_user)
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la récupération des entreprises"
        )


@router.get("/{group_id}/available-companies")
def get_available_companies(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Liste les entreprises sans groupe (Super Admin uniquement)."""
    try:
        return queries.get_available_companies(current_user)
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la récupération des entreprises"
        )


@router.get("/{group_id}/user-accesses")
def get_group_user_accesses(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Liste les accès utilisateurs aux entreprises du groupe (Super Admin uniquement)."""
    try:
        return queries.get_group_user_accesses(group_id, current_user)
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la récupération des accès"
        )


@router.get("/{group_id}/detailed-user-accesses")
def get_detailed_user_accesses(
    group_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Accès détaillés matriciels (Super Admin uniquement)."""
    try:
        return queries.get_detailed_user_accesses(group_id, current_user)
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la récupération des accès détaillés"
        )


# ----- POST / PATCH : écriture -----

@router.post("/", response_model=CompanyGroup, status_code=201)
def create_group(
    group: CompanyGroupCreate,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Crée un nouveau groupe (super_admin ou admin d'au moins 2 entreprises)."""
    if not current_user.is_super_admin:
        admin_companies = [
            acc for acc in current_user.accessible_companies
            if acc.role == "admin"
        ]
        if len(admin_companies) < 2:
            raise HTTPException(
                status_code=403,
                detail="Vous devez être admin d'au moins 2 entreprises pour créer un groupe",
            )
    try:
        dto = commands.create_group(group, current_user)
        return CompanyGroup(
            id=dto.id,
            group_name=dto.group_name,
            siren=dto.siren,
            description=dto.description,
            logo_url=dto.logo_url,
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )
    except Exception as e:
        _handle_application_errors(e, "Erreur lors de la création du groupe")


@router.patch("/{group_id}", response_model=CompanyGroup)
def update_group(
    group_id: str,
    group: CompanyGroupCreate,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Modifie un groupe (super_admin ou admin de toutes les entreprises du groupe)."""
    if not current_user.is_super_admin:
        company_ids = get_group_company_ids_for_permission_check(group_id)
        for cid in company_ids:
            if not current_user.is_admin_in_company(cid):
                raise HTTPException(
                    status_code=403,
                    detail="Vous devez être admin de toutes les entreprises du groupe",
                )
    try:
        dto = commands.update_group(group_id, group, current_user)
        return CompanyGroup(
            id=dto.id,
            group_name=dto.group_name,
            siren=dto.siren,
            description=dto.description,
            logo_url=dto.logo_url,
            is_active=dto.is_active,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )
    except Exception as e:
        _handle_application_errors(e, "Erreur lors de la mise à jour du groupe")


@router.post("/{group_id}/add-company/{company_id}")
def add_company_to_group(
    group_id: str,
    company_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Ajoute une entreprise à un groupe (admin de l'entreprise ou super_admin)."""
    if not current_user.is_super_admin:
        if not current_user.is_admin_in_company(company_id):
            raise HTTPException(
                status_code=403,
                detail="Vous devez être admin de l'entreprise",
            )
    try:
        result = commands.add_company_to_group(
            group_id, company_id, current_user
        )
        return {
            "message": result.message,
            "group_id": result.group_id,
            "company_id": result.company_id,
        }
    except Exception as e:
        _handle_application_errors(e, "Erreur lors de l'ajout au groupe")


@router.delete("/{group_id}/remove-company/{company_id}")
def remove_company_from_group(
    group_id: str,
    company_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Retire une entreprise d'un groupe (admin de l'entreprise ou super_admin)."""
    if not current_user.is_super_admin:
        if not current_user.is_admin_in_company(company_id):
            raise HTTPException(
                status_code=403,
                detail="Vous devez être admin de l'entreprise",
            )
    try:
        result = commands.remove_company_from_group(
            group_id, company_id, current_user
        )
        return {
            "message": result.message,
            "company_id": result.company_id,
        }
    except Exception as e:
        _handle_application_errors(e, "Erreur lors du retrait du groupe")


@router.post("/{group_id}/companies/bulk")
def bulk_add_companies_to_group(
    group_id: str,
    request: BulkAddCompaniesRequest,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Ajoute plusieurs entreprises au groupe (super_admin ou admin de toutes)."""
    if not request.company_ids:
        raise HTTPException(
            status_code=400,
            detail="La liste des entreprises est vide",
        )
    if not current_user.is_super_admin:
        for cid in request.company_ids:
            if not current_user.is_admin_in_company(cid):
                raise HTTPException(
                    status_code=403,
                    detail=f"Vous n'êtes pas admin de l'entreprise {cid}",
                )
    try:
        result = commands.bulk_add_companies_to_group(
            group_id, request.company_ids, current_user
        )
        return {
            "message": result.message,
            "success_count": result.success_count,
            "failed_count": result.failed_count,
            "failed_companies": result.failed_companies,
        }
    except Exception as e:
        _handle_application_errors(e, "Erreur lors de l'ajout en masse")


@router.post("/{group_id}/manage-user-access")
def manage_user_access_in_group(
    group_id: str,
    request: ManageUserAccessRequest,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Gère les accès d'un utilisateur aux entreprises du groupe (Super Admin uniquement)."""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux super administrateurs",
        )
    try:
        result = commands.manage_user_access_in_group(
            group_id, request, current_user
        )
        return {
            "message": result.message,
            "user_id": result.user_id,
            "user_email": result.user_email,
            "added_count": result.added_count,
            "updated_count": result.updated_count,
            "removed_count": result.removed_count,
        }
    except Exception as e:
        _handle_application_errors(e, "Erreur lors de la gestion des accès")


@router.delete("/{group_id}/user-access/{user_id}")
def remove_user_from_group(
    group_id: str,
    user_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Retire tous les accès d'un utilisateur aux entreprises du groupe (Super Admin uniquement)."""
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux super administrateurs",
        )
    try:
        result = commands.remove_user_from_group(
            group_id, user_id, current_user
        )
        return {
            "message": result.message,
            "removed_count": result.removed_count,
        }
    except Exception as e:
        _handle_application_errors(
            e, "Erreur lors de la suppression des accès"
        )


# ----- Alias RESTful -----

@router.post("/{group_id}/companies/{company_id}")
def add_company_to_group_alias(
    group_id: str,
    company_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Alias RESTful pour ajouter une entreprise au groupe."""
    return add_company_to_group(group_id, company_id, current_user)


@router.delete("/{group_id}/companies/{company_id}")
def remove_company_from_group_alias(
    group_id: str,
    company_id: str,
    current_user: CurrentUserForCompanyGroups = Depends(get_current_user),
):
    """Alias RESTful pour retirer une entreprise du groupe."""
    return remove_company_from_group(group_id, company_id, current_user)
