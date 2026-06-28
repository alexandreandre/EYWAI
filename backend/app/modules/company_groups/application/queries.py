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
from app.modules.company_groups.application.aggregates import (
    _month_range,
    aggregate_consolidated_dashboards,
    resolve_comparison_period,
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
from app.modules.dsn_import.infrastructure import payroll_totals_repository as dsn_totals_repo


def _period_key(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _parse_period_key(period: str) -> tuple[int, int] | None:
    try:
        year_raw, month_raw = str(period).split("-", 1)
        year, month = int(year_raw), int(month_raw)
    except (TypeError, ValueError):
        return None
    if month < 1 or month > 12:
        return None
    return year, month


def _latest_available_payroll_period(
    company_ids: List[str],
    *,
    requested_year: int,
    requested_month: int,
) -> tuple[int, int] | None:
    requested = _period_key(requested_year, requested_month)
    rows = dsn_totals_repo.list_by_companies(company_ids, limit_per_company=36)
    candidates: set[str] = set()
    for row in rows:
        period = str(row.get("period") or "")
        if period <= requested and float(row.get("gross_salary") or 0) > 0:
            candidates.add(period)
    if not candidates:
        return None
    return _parse_period_key(max(candidates))


def _total_gross(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    totals = payload.get("totals") or {}
    return float(totals.get("total_gross_salary") or 0)


def _mark_payroll_period_fallback(
    payload: dict,
    *,
    requested_year: int,
    requested_month: int,
    effective_year: int,
    effective_month: int,
) -> dict:
    metadata = dict(payload.get("metadata") or {})
    metadata.update(
        {
            "requested_year": requested_year,
            "requested_month": requested_month,
            "payroll_fallback_applied": True,
            "payroll_period_year": effective_year,
            "payroll_period_month": effective_month,
            "reference_year": effective_year,
            "reference_month": effective_month,
        }
    )
    return {**payload, "metadata": metadata}


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
    company_ids = (
        None if current_user.is_platform_admin else accessible
    )
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
    if not current_user.is_platform_admin:
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


def _fetch_consolidated_for_period(
    company_ids: List[str],
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> Any:
    """Charge et agrège les stats sur une plage de mois (fallback DSN à chaque mois)."""
    from app.modules.payroll.application.payroll_kpi_queries import (
        ConsolidatedPayrollContext,
        enrich_consolidated_with_dsn,
    )

    payroll_ctx = ConsolidatedPayrollContext.build(company_ids)

    def _load_month(year: int, month: int) -> Any:
        payload = call_get_group_consolidated_dashboard(company_ids, year, month)
        if not payload:
            return payload
        return enrich_consolidated_with_dsn(
            payload,
            company_ids,
            f"{year}-{month:02d}",
            ctx=payroll_ctx,
        )

    if (start_year, start_month) == (end_year, end_month):
        payload = _load_month(end_year, end_month)
        if not isinstance(payload, dict) or "totals" not in payload:
            return payload
        if _total_gross(payload) > 0:
            return payload

        fallback_period = _latest_available_payroll_period(
            company_ids,
            requested_year=end_year,
            requested_month=end_month,
        )
        if not fallback_period or fallback_period == (end_year, end_month):
            return payload

        fallback_year, fallback_month = fallback_period
        fallback_payload = _load_month(fallback_year, fallback_month)
        if not isinstance(fallback_payload, dict) or _total_gross(fallback_payload) <= 0:
            return payload
        return _mark_payroll_period_fallback(
            fallback_payload,
            requested_year=end_year,
            requested_month=end_month,
            effective_year=fallback_year,
            effective_month=fallback_month,
        )

    monthly: List[Any] = []
    for y, m in _month_range(start_year, start_month, end_year, end_month):
        payload = _load_month(y, m)
        if payload:
            monthly.append(payload)
    return aggregate_consolidated_dashboards(
        monthly,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )


def get_group_consolidated_stats(
    group_id: str,
    current_user: Any,
    year: Optional[int] = None,
    month: Optional[int] = None,
    start_year: Optional[int] = None,
    start_month: Optional[int] = None,
    end_year: Optional[int] = None,
    end_month: Optional[int] = None,
    compare_to: Optional[str] = None,
) -> Any:
    """Statistiques consolidées (RPC get_group_consolidated_dashboard)."""
    companies = company_group_repository.get_companies_for_group_stats(group_id)
    if not companies:
        raise LookupError("Aucune entreprise trouvée dans ce groupe")
    company_ids = get_company_ids_for_group(group_id, current_user)
    if not company_ids:
        raise PermissionError("Vous n'avez accès à aucune entreprise de ce groupe")

    if start_year is not None and start_month is not None and end_year is not None and end_month is not None:
        sy, sm, ey, em = start_year, start_month, end_year, end_month
    elif year is not None and month is not None:
        sy, sm, ey, em = year, month, year, month
    else:
        from datetime import datetime

        now = datetime.now()
        sy, sm, ey, em = now.year, now.month, now.year, now.month

    result = _fetch_consolidated_for_period(company_ids, sy, sm, ey, em)

    comparison_bounds = resolve_comparison_period(
        compare_to or "off",
        year=year,
        month=month,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )
    if comparison_bounds:
        csy, csm, cey, cem = comparison_bounds
        comparison = _fetch_consolidated_for_period(company_ids, csy, csm, cey, cem)
        result = {
            **result,
            "comparison": {
                "totals": comparison.get("totals", {}),
                "by_company": comparison.get("by_company", []),
            },
        }

    return result


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
    raw = call_get_group_payroll_evolution(
        company_ids, start_year, start_month, end_year, end_month
    )
    from app.modules.payroll.application.payroll_kpi_queries import (
        enrich_payroll_evolution_with_dsn,
    )

    return enrich_payroll_evolution_with_dsn(raw or [], company_ids)


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
    if not current_user.is_platform_admin:
        raise PermissionError("Accès réservé aux super administrateurs")
    groups = company_group_repository.list_all_active_ordered()
    with_stats = company_group_repository.get_groups_with_company_and_effectif(groups)
    return [_to_group_list_summary_dto(g) for g in with_stats]


def get_group_companies(group_id: str, current_user: Any) -> List[dict]:
    """Liste des entreprises d'un groupe (super_admin only)."""
    if not current_user.is_platform_admin:
        raise PermissionError("Accès réservé aux super administrateurs")
    return company_group_repository.get_companies_by_group_id(group_id)


def get_available_companies(current_user: Any) -> List[dict]:
    """Entreprises sans groupe (group_id null) pour affectation (super_admin only)."""
    if not current_user.is_platform_admin:
        raise PermissionError("Accès réservé aux super administrateurs")
    return company_group_repository.get_companies_without_group()


def get_group_user_accesses(group_id: str, current_user: Any) -> List[dict]:
    """Liste des accès utilisateurs aux entreprises du groupe (super_admin only)."""
    if not current_user.is_platform_admin:
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
        result.append(
            {
                "user_id": access["user_id"],
                "email": user_emails.get(access["user_id"], access["user_id"]),
                "first_name": profile.get("first_name"),
                "last_name": profile.get("last_name"),
                "company_id": access["company_id"],
                "company_name": company.get("company_name"),
                "role": access["role"],
            }
        )
    return result


def get_detailed_user_accesses(group_id: str, current_user: Any) -> dict:
    """Accès détaillés matriciels (companies + users avec accesses) (super_admin only)."""
    if not current_user.is_platform_admin:
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
