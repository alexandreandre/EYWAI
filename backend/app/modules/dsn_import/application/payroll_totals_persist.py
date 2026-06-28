"""Persiste les totaux DSN agrégés après commit d'un batch."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.modules.dsn_import.application.cumuls import aggregate_cumuls_by_company_period
from app.modules.dsn_import.infrastructure import payroll_totals_repository as totals_repo


def persist_batch_dsn_payroll_totals(
    cumul_items: List[Dict[str, Any]],
    *,
    resolve_company_id: Callable[[str], Optional[str]],
    batch_id: str,
) -> Dict[str, int]:
    """
    Upsert company_dsn_payroll_totals pour chaque (company, period) du batch.
    Retourne { company_id: nb_périodes }.
    """
    aggregated = aggregate_cumuls_by_company_period(
        cumul_items, resolve_company_id=resolve_company_id
    )
    counts: Dict[str, int] = {}
    for company_id, periods in aggregated.items():
        for period, totals in periods.items():
            totals_repo.upsert_totals(
                company_id,
                period,
                gross_salary=totals["gross_salary"],
                net_imposable=totals["net_imposable"],
                pas=totals["pas"],
                employee_charges=totals.get("employee_charges", 0.0),
                employer_charges=totals.get("employer_charges", 0.0),
                employee_count=totals["employee_count"],
                employees_with_gross=totals["employees_with_gross"],
                last_batch_id=batch_id,
            )
        counts[company_id] = len(periods)
    return counts
