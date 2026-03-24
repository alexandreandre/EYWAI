"""
Provider des appels RPC PostgreSQL pour les stats de groupe.

Implémente IGroupStatsProvider. Comportement identique à api/routers/company_groups.py.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from app.core.database import supabase

from app.modules.company_groups.domain.interfaces import IGroupStatsProvider


def _call_get_group_consolidated_dashboard(
    company_ids: List[str],
    reference_year: Optional[int] = None,
    reference_month: Optional[int] = None,
) -> Any:
    """RPC get_group_consolidated_dashboard. Retourne dashboard_res.data."""
    year = reference_year or datetime.now().year
    month = reference_month or datetime.now().month
    res = supabase.rpc(
        "get_group_consolidated_dashboard",
        {
            "p_company_ids": company_ids,
            "p_reference_year": year,
            "p_reference_month": month,
        },
    ).execute()
    return res.data


def _call_get_group_employees_stats(company_ids: List[str]) -> Any:
    """RPC get_group_employees_stats."""
    res = supabase.rpc(
        "get_group_employees_stats",
        {"p_company_ids": company_ids},
    ).execute()
    return res.data


def _call_get_group_payroll_evolution(
    company_ids: List[str],
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> Any:
    """RPC get_group_payroll_evolution."""
    res = supabase.rpc(
        "get_group_payroll_evolution",
        {
            "p_company_ids": company_ids,
            "p_start_year": start_year,
            "p_start_month": start_month,
            "p_end_year": end_year,
            "p_end_month": end_month,
        },
    ).execute()
    return res.data


def _call_get_group_company_comparison(
    company_ids: List[str],
    metric: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Any:
    """RPC get_group_company_comparison."""
    y = year or datetime.now().year
    m = month or datetime.now().month
    res = supabase.rpc(
        "get_group_company_comparison",
        {
            "p_company_ids": company_ids,
            "p_metric": metric,
            "p_year": y,
            "p_month": m,
        },
    ).execute()
    return res.data


class GroupStatsProvider(IGroupStatsProvider):
    """Implémentation du port IGroupStatsProvider via Supabase RPC."""

    def get_consolidated_dashboard(
        self,
        company_ids: List[str],
        reference_year: Optional[int] = None,
        reference_month: Optional[int] = None,
    ) -> Any:
        return _call_get_group_consolidated_dashboard(
            company_ids, reference_year, reference_month
        )

    def get_employees_stats(self, company_ids: List[str]) -> Any:
        return _call_get_group_employees_stats(company_ids)

    def get_payroll_evolution(
        self,
        company_ids: List[str],
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> Any:
        return _call_get_group_payroll_evolution(
            company_ids, start_year, start_month, end_year, end_month
        )

    def get_company_comparison(
        self,
        company_ids: List[str],
        metric: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Any:
        return _call_get_group_company_comparison(
            company_ids, metric, year, month
        )


# Instance pour injection ou import direct. Compatibilité avec l'usage par fonctions.
group_stats_provider = GroupStatsProvider()


# Réexport des fonctions pour compatibilité avec application/queries.py (appels directs).
def call_get_group_consolidated_dashboard(
    company_ids: List[str],
    reference_year: Optional[int] = None,
    reference_month: Optional[int] = None,
) -> Any:
    return _call_get_group_consolidated_dashboard(
        company_ids, reference_year, reference_month
    )


def call_get_group_employees_stats(company_ids: List[str]) -> Any:
    return _call_get_group_employees_stats(company_ids)


def call_get_group_payroll_evolution(
    company_ids: List[str],
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> Any:
    return _call_get_group_payroll_evolution(
        company_ids, start_year, start_month, end_year, end_month
    )


def call_get_group_company_comparison(
    company_ids: List[str],
    metric: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Any:
    return _call_get_group_company_comparison(company_ids, metric, year, month)
