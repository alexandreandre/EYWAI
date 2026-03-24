"""
Requêtes (cas d'usage lecture) du module company_groups.

Logique extraite de api/routers/company_groups.py ; comportement identique.
Délégation à l'infrastructure (repository, providers, mappers).
"""
from __future__ import annotations

from typing import Any, List, Optional

from app.modules.company_groups.application.dto import (
    GroupListSummaryDto,
    GroupWithCompaniesDto,
)
from app.modules.company_groups.application.service import (
    get_accessible_company_ids,
    get_company_ids_for_group,
)
from app.modules.company_groups.infrastructure.mappers import (
    row_to_group_with_companies,
    rows_to_groups_with_companies,
)
from app.modules.company_groups.infrastructure.providers import (
    call_get_group_company_comparison,
    call_get_group_consolidated_dashboard,
    call_get_group_employees_stats,
    call_get_group_payroll_evolution,
)
from app.modules.company_groups.infrastructure.repository import (
    CompanyGroupRepository,
    company_group_repository,
)


def _to_group_with_companies_dto(g: dict) -> GroupWithCompaniesDto:
    """Construit un GroupWithCompaniesDto depuis un dict (sortie mapper)."""
    return GroupWithCompaniesDto(
        id=g["id"],
        group_name=g["group_name"],
        siren=g.get("siren"),
        description=g.get("description"),
        logo_url=g.get("logo_url"),
        is_active=g["is_active"],
        created_at=g["created_at"],
        updated_at=g["updated_at"],
        companies=g.get("companies", []),
    )


def _to_group_list_summary_dto(g: dict) -> GroupListSummaryDto:
    """Construit un GroupListSummaryDto depuis un dict (sortie repository)."""
    return GroupListSummaryDto(
        id=g["id"],
        group_name=g["group_name"],
        description=g.get("description"),
        created_at=g["created_at"],
        company_count=g["company_count"],
        total_employees=g["total_employees"],
    )


def get_my_groups(current_user: Any) -> List[GroupWithCompaniesDto]:
    """Liste les groupes auxquels l'utilisateur a accès (via accessible_companies)."""
    accessible = get_accessible_company_ids(current_user)
    company_ids = None if (getattr(current_user, "is_super_admin", False)) else accessible
    if company_ids is not None and len(company_ids) == 0:
        return []
    rows = company_group_repository.list_groups_with_companies(company_ids)
    aggregated = rows_to_groups_with_companies(rows)
    return [_to_group_with_companies_dto(g) for g in aggregated]


def get_group_details(group_id: str, current_user: Any) -> GroupWithCompaniesDto:
    """Détail d'un groupe + entreprises (filtrées par accès)."""
    row = company_group_repository.get_by_id_with_companies(group_id)
    if not row:
        raise LookupError("Groupe non trouvé")
    if not getattr(current_user, "is_super_admin", False):
        companies = row.get("companies") or []
        if isinstance(companies, dict):
            companies = [companies]
        accessible_ids = set(get_accessible_company_ids(current_user))
        filtered = [c for c in companies if c.get("id") in accessible_ids]
        if not filtered:
            raise PermissionError("Vous n'avez accès à aucune entreprise de ce groupe")
        row = {**row, "companies": filtered}
    g = row_to_group_with_companies(row)
    return _to_group_with_companies_dto(g)


def get_group_consolidated_stats(
    group_id: str,
    current_user: Any,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Any:
    """Statistiques consolidées (RPC get_group_consolidated_dashboard)."""
    companies = company_group_repository.get_companies_for_group_stats(group_id)
    if not companies:
        raise LookupError("Aucune entreprise trouvée dans ce groupe")
    company_ids = get_company_ids_for_group(group_id, current_user)
    if not company_ids:
        raise PermissionError("Vous n'avez accès à aucune entreprise de ce groupe")
    return call_get_group_consolidated_dashboard(company_ids, year, month)


def get_group_employees_stats(group_id: str, current_user: Any) -> Any:
    """Stats employés par entreprise (RPC get_group_employees_stats)."""
    company_ids = get_company_ids_for_group(group_id, current_user)
    if not company_ids:
        raise PermissionError("Aucune entreprise accessible dans ce groupe")
    return call_get_group_employees_stats(company_ids)


def get_group_payroll_evolution(
    group_id: str,
    current_user: Any,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> Any:
    """Évolution masse salariale (RPC get_group_payroll_evolution)."""
    company_ids = get_company_ids_for_group(group_id, current_user)
    if not company_ids:
        raise PermissionError("Aucune entreprise accessible dans ce groupe")
    return call_get_group_payroll_evolution(
        company_ids, start_year, start_month, end_year, end_month
    )


def get_group_company_comparison(
    group_id: str,
    current_user: Any,
    metric: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Any:
    """Comparaison inter-entreprises (RPC get_group_company_comparison)."""
    company_ids = get_company_ids_for_group(group_id, current_user)
    if not company_ids:
        raise PermissionError("Aucune entreprise accessible dans ce groupe")
    return call_get_group_company_comparison(company_ids, metric, year, month)


def get_all_groups(current_user: Any) -> List[GroupListSummaryDto]:
    """Liste tous les groupes avec company_count et total_employees (super_admin only)."""
    if not getattr(current_user, "is_super_admin", False):
        raise PermissionError("Accès réservé aux super administrateurs")
    groups = company_group_repository.list_all_active_ordered()
    with_stats = company_group_repository.get_groups_with_company_and_effectif(groups)
    return [_to_group_list_summary_dto(g) for g in with_stats]


def get_group_companies(group_id: str, current_user: Any) -> List[dict]:
    """Liste des entreprises d'un groupe (super_admin only)."""
    if not getattr(current_user, "is_super_admin", False):
        raise PermissionError("Accès réservé aux super administrateurs")
    return company_group_repository.get_companies_by_group_id(group_id)


def get_available_companies(current_user: Any) -> List[dict]:
    """Entreprises sans groupe (group_id null) pour affectation (super_admin only)."""
    if not getattr(current_user, "is_super_admin", False):
        raise PermissionError("Accès réservé aux super administrateurs")
    return company_group_repository.get_companies_without_group()


def get_group_user_accesses(group_id: str, current_user: Any) -> List[dict]:
    """Liste des accès utilisateurs aux entreprises du groupe (super_admin only)."""
    if not getattr(current_user, "is_super_admin", False):
        raise PermissionError("Accès réservé aux super administrateurs")
    company_ids = company_group_repository.get_company_ids_by_group_id(group_id)
    if not company_ids:
        return []
    accesses = company_group_repository.get_user_accesses_for_companies(company_ids)
    user_ids = list({a["user_id"] for a in accesses})
    user_emails = CompanyGroupRepository.get_user_emails_map(user_ids)
    result = []
    for access in accesses:
        profile = access.get("profiles") or {}
        company = access.get("companies") or {}
        result.append({
            "user_id": access["user_id"],
            "email": user_emails.get(access["user_id"], access["user_id"]),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "company_id": access["company_id"],
            "company_name": company.get("company_name"),
            "role": access["role"],
        })
    return result


def get_detailed_user_accesses(group_id: str, current_user: Any) -> dict:
    """Accès détaillés matriciels (companies + users avec accesses) (super_admin only)."""
    if not getattr(current_user, "is_super_admin", False):
        raise PermissionError("Accès réservé aux super administrateurs")
    companies = company_group_repository.get_companies_by_group_id(
        group_id, columns="id, company_name, siret"
    )
    if not companies:
        return {"companies": [], "users": []}
    company_ids = [c["id"] for c in companies]
    accesses = company_group_repository.get_detailed_accesses_for_companies(company_ids)
    user_ids = list({a["user_id"] for a in accesses})
    user_emails = CompanyGroupRepository.get_user_emails_map(user_ids)
    users_dict = {}
    for access in accesses:
        user_id = access["user_id"]
        profile = access.get("profiles") or {}
        if user_id not in users_dict:
            users_dict[user_id] = {
                "user_id": user_id,
                "email": user_emails.get(user_id, user_id),
                "first_name": profile.get("first_name"),
                "last_name": profile.get("last_name"),
                "accesses": {},
            }
        users_dict[user_id]["accesses"][access["company_id"]] = {
            "role": access["role"],
            "is_primary": access.get("is_primary", False),
        }
    return {"companies": companies, "users": list(users_dict.values())}
