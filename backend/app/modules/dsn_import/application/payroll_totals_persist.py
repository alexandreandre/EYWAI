"""Persiste les totaux DSN agrégés après commit d'un batch."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.modules.dsn_import.application.cumuls import aggregate_cumuls_by_company_period
from app.modules.dsn_import.infrastructure import payroll_totals_repository as totals_repo
from app.modules.dsn_import.infrastructure import repository as repo


def build_resolve_company_id_for_totals(
    *,
    company_by_siret: Optional[Dict[str, str]] = None,
    target_company_id: Optional[str] = None,
) -> Callable[[str], Optional[str]]:
    """Résout le SIRET DSN vers company_id (mapping commit ou rattachement manuel)."""
    mapping = {str(k): str(v) for k, v in (company_by_siret or {}).items() if k and v}
    target_cid = str(target_company_id) if target_company_id else None

    def resolve(siret: str) -> Optional[str]:
        clean = str(siret or "").strip()
        if clean and clean in mapping:
            return mapping[clean]
        if target_cid:
            return target_cid
        if clean:
            co = repo.find_company_by_siret(clean)
            return str(co["id"]) if co else None
        return None

    return resolve


def build_resolve_company_id_from_batch(batch_id: str) -> Callable[[str], Optional[str]]:
    """Reconstruit le resolver entreprise depuis un batch committed (backfill)."""
    batch = repo.get_batch(batch_id)
    summary = (batch or {}).get("summary") or {}
    company_by_siret: Dict[str, str] = {}
    for item in repo.list_items(batch_id):
        if item.get("item_type") != "establishment":
            continue
        payload = item.get("mapped_payload") or {}
        siret = str(payload.get("siret") or "").strip()
        target_id = item.get("target_id")
        if siret and target_id:
            company_by_siret[siret] = str(target_id)
    return build_resolve_company_id_for_totals(
        company_by_siret=company_by_siret,
        target_company_id=summary.get("target_company_id"),
    )


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
