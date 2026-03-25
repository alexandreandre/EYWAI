"""
Commandes (cas d'usage écriture) du module company_groups.

Logique extraite de api/routers/company_groups.py ; comportement identique.
Les vérifications d'autorisation (super_admin, admin de X entreprises) restent
à faire côté appelant (router) ; les commandes présument que l'appelant a vérifié.
"""

from __future__ import annotations

from typing import Any, List

from app.modules.company_groups.application.dto import (
    AddRemoveCompanyResultDto,
    BulkAddCompaniesResultDto,
    CompanyGroupDto,
    ManageUserAccessResultDto,
    RemoveUserFromGroupResultDto,
)
from app.modules.company_groups.infrastructure.repository import (
    CompanyGroupRepository,
    company_group_repository,
)


def _row_to_company_group_dto(row: dict) -> CompanyGroupDto:
    """Construit CompanyGroupDto depuis une ligne company_groups."""
    return CompanyGroupDto(
        id=row["id"],
        group_name=row["group_name"],
        siren=row.get("siren"),
        description=row.get("description"),
        logo_url=row.get("logo_url"),
        is_active=row.get("is_active", True),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_group(data: Any, current_user: Any) -> CompanyGroupDto:
    """
    Crée un nouveau groupe.
    L'appelant doit avoir vérifié : super_admin ou admin d'au moins 2 entreprises.
    """
    payload = {
        "group_name": data.group_name,
        "siren": data.siren,
        "description": data.description,
        "logo_url": data.logo_url,
        "is_active": True,
    }
    row = company_group_repository.create(payload)
    if not row:
        raise RuntimeError("Erreur lors de la création du groupe")
    return _row_to_company_group_dto(row)


def update_group(group_id: str, data: Any, current_user: Any) -> CompanyGroupDto:
    """
    Met à jour un groupe.
    L'appelant doit avoir vérifié : super_admin ou admin de toutes les entreprises du groupe.
    """
    payload = {
        "group_name": data.group_name,
        "siren": data.siren,
        "description": data.description,
        "logo_url": data.logo_url,
    }
    row = company_group_repository.update(group_id, payload)
    if not row:
        raise LookupError("Groupe non trouvé")
    return _row_to_company_group_dto(row)


def add_company_to_group(
    group_id: str, company_id: str, current_user: Any
) -> AddRemoveCompanyResultDto:
    """
    Ajoute une entreprise à un groupe.
    L'appelant doit avoir vérifié : admin de l'entreprise ou super_admin.
    """
    if not company_group_repository.exists(group_id):
        raise LookupError("Groupe non trouvé")
    ok = company_group_repository.set_company_group(company_id, group_id)
    if not ok:
        raise LookupError("Entreprise non trouvée")
    return AddRemoveCompanyResultDto(
        message="Entreprise ajoutée au groupe avec succès",
        group_id=group_id,
        company_id=company_id,
    )


def remove_company_from_group(
    group_id: str, company_id: str, current_user: Any
) -> AddRemoveCompanyResultDto:
    """
    Retire une entreprise d'un groupe.
    L'appelant doit avoir vérifié : admin de l'entreprise ou super_admin.
    """
    ok = company_group_repository.set_company_group_with_current(
        company_id, None, group_id
    )
    if not ok:
        raise LookupError("Entreprise non trouvée ou pas dans ce groupe")
    return AddRemoveCompanyResultDto(
        message="Entreprise retirée du groupe avec succès",
        company_id=company_id,
    )


def bulk_add_companies_to_group(
    group_id: str, company_ids: List[str], current_user: Any
) -> BulkAddCompaniesResultDto:
    """
    Ajoute plusieurs entreprises au groupe.
    L'appelant doit avoir vérifié : super_admin ou admin de toutes les entreprises listées.
    """
    if not company_group_repository.exists(group_id):
        raise LookupError("Groupe non trouvé")
    success_count = 0
    failed_companies = []
    for cid in company_ids:
        try:
            ok = company_group_repository.set_company_group(cid, group_id)
            if ok:
                success_count += 1
            else:
                failed_companies.append(cid)
        except Exception:
            failed_companies.append(cid)
    return BulkAddCompaniesResultDto(
        message=f"{success_count} entreprise(s) ajoutée(s) au groupe",
        success_count=success_count,
        failed_count=len(failed_companies),
        failed_companies=failed_companies,
    )


def manage_user_access_in_group(
    group_id: str, request: Any, current_user: Any
) -> ManageUserAccessResultDto:
    """
    Gère les accès d'un utilisateur aux entreprises du groupe.
    Super admin only (vérifié par l'appelant).
    """
    if not request.accesses:
        raise ValueError("Au moins un accès doit être défini")
    valid_company_ids = company_group_repository.get_company_ids_by_group_id(group_id)
    valid_set = set(valid_company_ids)
    for acc in request.accesses:
        if acc.company_id not in valid_set:
            raise ValueError(
                f"L'entreprise {acc.company_id} n'appartient pas à ce groupe"
            )
    user = CompanyGroupRepository.get_user_by_email(request.user_email)
    if not user:
        raise LookupError(f"Utilisateur avec l'email {request.user_email} non trouvé")
    user_id = user["id"]
    if request.first_name or request.last_name:
        company_group_repository.update_user_profile(
            user_id, request.first_name, request.last_name
        )
    existing = company_group_repository.get_existing_user_accesses(
        user_id, valid_company_ids
    )
    requested_ids = {acc.company_id for acc in request.accesses}
    added_count = 0
    updated_count = 0
    is_primary_for_next = company_group_repository.count_user_accesses(user_id) == 0
    for acc in request.accesses:
        if acc.company_id in existing:
            if existing[acc.company_id] != acc.role:
                company_group_repository.update_user_company_access_role(
                    user_id, acc.company_id, acc.role
                )
                updated_count += 1
        else:
            company_group_repository.insert_user_company_access(
                user_id, acc.company_id, acc.role, is_primary_for_next
            )
            added_count += 1
            is_primary_for_next = False
    removed_count = 0
    for existing_company_id in existing:
        if existing_company_id not in requested_ids:
            company_group_repository.delete_user_company_accesses(
                user_id, [existing_company_id]
            )
            removed_count += 1
    return ManageUserAccessResultDto(
        message="Accès utilisateur mis à jour avec succès",
        user_id=user_id,
        user_email=request.user_email,
        added_count=added_count,
        updated_count=updated_count,
        removed_count=removed_count,
    )


def remove_user_from_group(
    group_id: str, user_id: str, current_user: Any
) -> RemoveUserFromGroupResultDto:
    """
    Retire tous les accès d'un utilisateur aux entreprises du groupe.
    Super admin only (vérifié par l'appelant).
    """
    company_ids = company_group_repository.get_company_ids_by_group_id(group_id)
    if not company_ids:
        return RemoveUserFromGroupResultDto(
            message="Aucune entreprise dans ce groupe",
            removed_count=0,
        )
    removed_count = company_group_repository.delete_user_company_accesses(
        user_id, company_ids
    )
    return RemoveUserFromGroupResultDto(
        message=f"{removed_count} accès supprimé(s) pour l'utilisateur",
        removed_count=removed_count,
    )
