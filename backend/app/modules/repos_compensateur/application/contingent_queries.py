"""
Queries suivi contingent : overview, détail employé, KPIs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.modules.repos_compensateur.domain.contingent_rules import (
    ContingentEmployeeInput,
    ContingentSettings,
    aggregate_contingent_kpis,
    compute_contingent_breakdown,
    compute_monthly_breakdown,
)
from app.modules.repos_compensateur.infrastructure.providers import (
    get_bulletins_par_mois_par_employe,
    get_payroll_events_par_mois_par_employe,
)
from app.modules.repos_compensateur.infrastructure.queries import (
    get_employees_for_company,
    get_validated_repos_requests,
)
from app.modules.repos_compensateur.infrastructure.settings_repository import (
    get_adjustments_by_company_year,
    get_contingent_settings,
    get_contingent_settings_row,
)


def _parse_hire_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.date()
    return None


def _breakdown_to_dict(breakdown) -> dict[str, Any]:
    return {
        "structural_hours": breakdown.structural_hours,
        "paid_hours": breakdown.paid_hours,
        "pause_deduction": breakdown.pause_deduction,
        "manual_adjustment": breakdown.manual_adjustment,
        "rcr_hours": breakdown.rcr_hours,
        "consumed_hours": breakdown.consumed_hours,
        "total_for_ceiling": breakdown.total_for_ceiling,
        "margin_hours": breakdown.margin_hours,
        "legal_cor_excess": breakdown.legal_cor_excess,
        "management_contingent": breakdown.management_contingent,
        "legal_cor_contingent": breakdown.legal_cor_contingent,
        "usage_percent": breakdown.usage_percent,
        "status": breakdown.status,
    }


def get_contingent_overview(
    company_id: str,
    year: int,
    reference_date: date,
) -> dict[str, Any]:
    settings = get_contingent_settings(company_id)
    employees = get_employees_for_company(company_id)
    employee_ids = [str(e["id"]) for e in employees]

    bulletins = get_bulletins_par_mois_par_employe(company_id, year, employee_ids)
    payroll_events_map = get_payroll_events_par_mois_par_employe(
        company_id, year, employee_ids
    )
    adjustments = get_adjustments_by_company_year(company_id, year)
    repos_requests = get_validated_repos_requests(company_id, employee_ids)

    rows: list[dict[str, Any]] = []
    breakdowns = []
    for emp in employees:
        emp_id = str(emp["id"])
        emp_input = ContingentEmployeeInput(
            employee_id=emp_id,
            first_name=str(emp.get("first_name") or ""),
            last_name=str(emp.get("last_name") or ""),
            hire_date=_parse_hire_date(emp.get("hire_date")),
            duree_hebdomadaire=(
                float(emp["duree_hebdomadaire"])
                if emp.get("duree_hebdomadaire") is not None
                else None
            ),
            opening_balance_hours=adjustments.get(emp_id, 0.0),
            validated_repos_requests=repos_requests.get(emp_id, []),
            bulletins_par_mois=bulletins.get(emp_id, {}),
            payroll_events_par_mois=payroll_events_map.get(emp_id, {}),
        )
        breakdown = compute_contingent_breakdown(
            emp_input, settings, year, reference_date
        )
        breakdowns.append(breakdown)
        rows.append(
            {
                "employee_id": emp_id,
                "first_name": emp_input.first_name,
                "last_name": emp_input.last_name,
                "hire_date": (
                    emp_input.hire_date.isoformat() if emp_input.hire_date else None
                ),
                **_breakdown_to_dict(breakdown),
            }
        )

    rows.sort(key=lambda r: (r["last_name"], r["first_name"]))
    kpis = aggregate_contingent_kpis(breakdowns)

    return {
        "company_id": company_id,
        "year": year,
        "reference_date": reference_date.isoformat(),
        "settings": _settings_to_api(get_contingent_settings_row(company_id)),
        "kpis": kpis,
        "employees": rows,
    }


def get_contingent_employee_detail(
    company_id: str,
    employee_id: str,
    year: int,
    reference_date: date,
) -> dict[str, Any]:
    settings = get_contingent_settings(company_id)
    employees = get_employees_for_company(company_id)
    emp = next((e for e in employees if str(e["id"]) == employee_id), None)
    if not emp:
        return {}

    bulletins = get_bulletins_par_mois_par_employe(company_id, year, [employee_id])
    payroll_events_map = get_payroll_events_par_mois_par_employe(
        company_id, year, [employee_id]
    )
    adjustments = get_adjustments_by_company_year(company_id, year)
    repos_requests = get_validated_repos_requests(company_id, [employee_id])

    emp_input = ContingentEmployeeInput(
        employee_id=employee_id,
        first_name=str(emp.get("first_name") or ""),
        last_name=str(emp.get("last_name") or ""),
        hire_date=_parse_hire_date(emp.get("hire_date")),
        duree_hebdomadaire=(
            float(emp["duree_hebdomadaire"])
            if emp.get("duree_hebdomadaire") is not None
            else None
        ),
        opening_balance_hours=adjustments.get(employee_id, 0.0),
        validated_repos_requests=repos_requests.get(employee_id, []),
        bulletins_par_mois=bulletins.get(employee_id, {}),
        payroll_events_par_mois=payroll_events_map.get(employee_id, {}),
    )
    breakdown = compute_contingent_breakdown(
        emp_input, settings, year, reference_date
    )
    monthly = compute_monthly_breakdown(emp_input, settings, year, reference_date)

    from app.modules.repos_compensateur.infrastructure.settings_repository import (
        get_adjustment,
    )

    adjustment = get_adjustment(company_id, employee_id, year)

    return {
        "employee_id": employee_id,
        "first_name": emp_input.first_name,
        "last_name": emp_input.last_name,
        "hire_date": (
            emp_input.hire_date.isoformat() if emp_input.hire_date else None
        ),
        "year": year,
        "reference_date": reference_date.isoformat(),
        "breakdown": _breakdown_to_dict(breakdown),
        "monthly": [
            {
                "month": m.month,
                "paid_hours": m.paid_hours,
                "cumulative_consumed": m.cumulative_consumed,
                "cumulative_total": m.cumulative_total,
            }
            for m in monthly
        ],
        "adjustment": {
            "opening_balance_hours": float(
                adjustment.get("opening_balance_hours", 0) if adjustment else 0
            ),
            "note": adjustment.get("note") if adjustment else None,
        },
        "settings": _settings_to_api(get_contingent_settings_row(company_id)),
    }


def _settings_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": str(row.get("company_id", "")),
        "legal_cor_contingent_hours": float(
            row.get("legal_cor_contingent_hours") or 220
        ),
        "management_contingent_hours": (
            float(row["management_contingent_hours"])
            if row.get("management_contingent_hours") is not None
            else None
        ),
        "hours_per_rest_day": float(row.get("hours_per_rest_day") or 7),
        "include_structural_hours": bool(row.get("include_structural_hours", True)),
        "pause_deduction_enabled": bool(row.get("pause_deduction_enabled", False)),
        "pause_hs_deduction_per_workday": float(
            row.get("pause_hs_deduction_per_workday") or 0.058765
        ),
        "workdays_per_year_for_pause": int(
            row.get("workdays_per_year_for_pause") or 260
        ),
    }
