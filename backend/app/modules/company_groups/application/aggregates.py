"""
Agrégation multi-mois des statistiques consolidées de groupe.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _month_range(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> List[Tuple[int, int]]:
    """Liste (année, mois) inclusive entre deux bornes."""
    months: List[Tuple[int, int]] = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _empty_dashboard(year: int, month: int = 0) -> Dict[str, Any]:
    return {
        "metadata": {
            "reference_year": year,
            "reference_month": month,
            "generated_at": datetime.utcnow().isoformat(),
            "company_count": 0,
        },
        "totals": {
            "total_employees": 0,
            "total_employees_excluding_rh": 0,
            "total_rh": 0,
            "total_payslip_count": 0,
            "total_gross_salary": 0,
            "total_net_salary": 0,
            "total_employer_charges": 0,
            "average_gross_per_company": 0,
            "average_employees_per_company": 0,
        },
        "by_company": [],
    }


def aggregate_consolidated_dashboards(
    monthly_payloads: List[Dict[str, Any]],
    *,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> Dict[str, Any]:
    """
    Agrège plusieurs snapshots mensuels.

    - Montants paie : somme sur la période.
    - Effectifs : moyenne des effectifs mensuels par entreprise (plus représentatif qu'un max).
    """
    valid = [p for p in monthly_payloads if p and p.get("by_company")]
    if not valid:
        return _empty_dashboard(end_year, 0)

    company_acc: Dict[str, Dict[str, Any]] = {}
    month_count_by_company: Dict[str, int] = {}

    for month_data in valid:
        for company in month_data.get("by_company") or []:
            cid = company.get("company_id") or company.get("id")
            if not cid:
                continue
            existing = company_acc.get(cid)
            if existing is None:
                company_acc[cid] = deepcopy(company)
                company_acc[cid]["company_id"] = cid
                month_count_by_company[cid] = 1
                existing = company_acc[cid]
            else:
                existing["payslip_count"] = existing.get("payslip_count", 0) + company.get(
                    "payslip_count", 0
                )
                existing["gross_salary"] = existing.get("gross_salary", 0) + company.get(
                    "gross_salary", 0
                )
                existing["net_salary"] = existing.get("net_salary", 0) + company.get(
                    "net_salary", 0
                )
                existing["employer_charges"] = existing.get(
                    "employer_charges", 0
                ) + company.get("employer_charges", 0)
                existing["_sum_total_employees"] = existing.get(
                    "_sum_total_employees", existing.get("total_employee_count", 0)
                ) + company.get("total_employee_count", 0)
                existing["_sum_employee_count"] = existing.get(
                    "_sum_employee_count", existing.get("employee_count", 0)
                ) + company.get("employee_count", 0)
                existing["_sum_rh_count"] = existing.get(
                    "_sum_rh_count", existing.get("rh_count", 0)
                ) + company.get("rh_count", 0)
                month_count_by_company[cid] = month_count_by_company.get(cid, 1) + 1

    by_company: List[Dict[str, Any]] = []
    for cid, row in company_acc.items():
        n = month_count_by_company.get(cid, 1)
        if "_sum_total_employees" in row:
            row["total_employee_count"] = round(row["_sum_total_employees"] / n)
            row["employee_count"] = round(row["_sum_employee_count"] / n)
            row["rh_count"] = round(row["_sum_rh_count"] / n)
            row.pop("_sum_total_employees", None)
            row.pop("_sum_employee_count", None)
            row.pop("_sum_rh_count", None)
        by_company.append(row)

    totals = {
        "total_employees": sum(c.get("total_employee_count", 0) for c in by_company),
        "total_employees_excluding_rh": sum(c.get("employee_count", 0) for c in by_company),
        "total_rh": sum(c.get("rh_count", 0) for c in by_company),
        "total_payslip_count": sum(c.get("payslip_count", 0) for c in by_company),
        "total_gross_salary": sum(c.get("gross_salary", 0) for c in by_company),
        "total_net_salary": sum(c.get("net_salary", 0) for c in by_company),
        "total_employer_charges": sum(c.get("employer_charges", 0) for c in by_company),
        "average_gross_per_company": 0.0,
        "average_employees_per_company": 0.0,
    }
    if by_company:
        totals["average_gross_per_company"] = totals["total_gross_salary"] / len(by_company)
        totals["average_employees_per_company"] = totals["total_employees"] / len(
            by_company
        )

    return {
        "metadata": {
            "reference_year": end_year,
            "reference_month": 0,
            "generated_at": datetime.utcnow().isoformat(),
            "company_count": len(by_company),
            "period_start_year": start_year,
            "period_start_month": start_month,
            "period_end_year": end_year,
            "period_end_month": end_month,
        },
        "totals": totals,
        "by_company": by_company,
    }


def resolve_comparison_period(
    compare_to: str,
    *,
    year: Optional[int],
    month: Optional[int],
    start_year: Optional[int],
    start_month: Optional[int],
    end_year: Optional[int],
    end_month: Optional[int],
) -> Optional[Tuple[int, int, int, int]]:
    """Retourne (start_year, start_month, end_year, end_month) pour la période de comparaison."""
    now = datetime.now()
    ref_year = year or end_year or now.year
    ref_month = month or end_month or now.month

    if compare_to == "off" or not compare_to:
        return None

    if compare_to == "previous_month":
        if start_year and start_month and end_year and end_month:
            # Même durée, décalée d'un mois avant le début
            months = _month_range(start_year, start_month, end_year, end_month)
            span = len(months)
            sy, sm = start_year, start_month
            for _ in range(span):
                sm -= 1
                if sm < 1:
                    sm = 12
                    sy -= 1
            ey, em = sy, sm
            for _ in range(span - 1):
                em += 1
                if em > 12:
                    em = 1
                    ey += 1
            return sy, sm, ey, em
        pm = ref_month - 1
        py = ref_year
        if pm < 1:
            pm = 12
            py -= 1
        return py, pm, py, pm

    if compare_to == "previous_year":
        if start_year and start_month and end_year and end_month:
            return start_year - 1, start_month, end_year - 1, end_month
        return ref_year - 1, ref_month, ref_year - 1, ref_month

    if compare_to == "ytd_previous_year":
        return ref_year - 1, 1, ref_year - 1, ref_month

    return None
