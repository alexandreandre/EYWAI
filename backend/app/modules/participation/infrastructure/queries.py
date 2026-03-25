"""
Requêtes métier pour les données employés (participation).

Agrégation depuis employees, employee_schedules, payslips.
Délègue les règles métier pures au domain (présence, ancienneté, extraction cumuls).
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.participation.domain.rules import (
    compute_presence_days_for_schedules,
    compute_seniority_years,
    extract_annual_salary_from_cumuls,
)


def fetch_employee_participation_data(
    company_id: str,
    year: int,
) -> List[Dict[str, Any]]:
    """
    Récupère et calcule les données employés pour le simulateur Participation & Intéressement :
    - Salaire annuel : employee_schedules.cumuls puis fallback payslips (règle domain extract_annual_salary_from_cumuls).
    - Jours de présence : domain compute_presence_days_for_schedules.
    - Ancienneté : domain compute_seniority_years.
    Retourne une liste de dicts : employee_id, first_name, last_name, annual_salary,
    presence_days, seniority_years, has_real_salary, has_real_presence.
    """
    employees_res = (
        supabase.table("employees")
        .select("id, first_name, last_name, hire_date, salaire_de_base")
        .eq("company_id", company_id)
        .execute()
    )
    employees = employees_res.data or []
    if not employees:
        return []

    employee_ids = [emp["id"] for emp in employees]
    salary_by_employee: Dict[str, float] = {}

    schedules_cumuls_res = (
        supabase.table("employee_schedules")
        .select("employee_id, month, cumuls")
        .eq("company_id", company_id)
        .eq("year", year)
        .in_("employee_id", employee_ids)
        .order("month")
        .execute()
    )
    schedules_cumuls = schedules_cumuls_res.data or []
    for schedule in schedules_cumuls:
        employee_id = schedule["employee_id"]
        cumuls = schedule.get("cumuls", {})
        brut_total = extract_annual_salary_from_cumuls(cumuls)
        if brut_total > 0:
            salary_by_employee[employee_id] = brut_total

    payslips_res = (
        supabase.table("payslips")
        .select("id, employee_id, month, payslip_data")
        .eq("company_id", company_id)
        .eq("year", year)
        .order("month")
        .execute()
    )
    payslips = payslips_res.data or []
    for payslip in payslips:
        employee_id = payslip["employee_id"]
        if employee_id not in salary_by_employee:
            payslip_data = payslip.get("payslip_data", {})
            if isinstance(payslip_data, dict):
                cumuls = payslip_data.get("cumuls", {})
                brut_total = extract_annual_salary_from_cumuls(cumuls)
                if brut_total > 0:
                    salary_by_employee[employee_id] = brut_total
                    continue
                brut = float(payslip_data.get("salaire_brut", 0) or 0)
                if brut > 0:
                    salary_by_employee[employee_id] = (
                        salary_by_employee.get(employee_id, 0) + brut
                    )

    schedules_res = (
        supabase.table("employee_schedules")
        .select("employee_id, month, planned_calendar, actual_hours")
        .eq("company_id", company_id)
        .eq("year", year)
        .in_("employee_id", employee_ids)
        .execute()
    )
    schedules = schedules_res.data or []
    presence_by_employee: Dict[str, int] = {}

    for employee in employees:
        employee_id = employee["id"]
        employee_schedules = [s for s in schedules if s["employee_id"] == employee_id]
        presence_days = compute_presence_days_for_schedules(employee_schedules)
        presence_by_employee[employee_id] = presence_days

    result: List[Dict[str, Any]] = []
    for employee in employees:
        employee_id = employee["id"]
        annual_salary = salary_by_employee.get(employee_id, 0)
        presence_days = presence_by_employee.get(employee_id, 0)
        seniority_years = compute_seniority_years(employee.get("hire_date"))
        has_real_salary = annual_salary > 0
        has_real_presence = presence_days > 0
        result.append(
            {
                "employee_id": employee_id,
                "first_name": employee.get("first_name", ""),
                "last_name": employee.get("last_name", ""),
                "annual_salary": round(annual_salary, 2),
                "presence_days": presence_days,
                "seniority_years": seniority_years,
                "has_real_salary": has_real_salary,
                "has_real_presence": has_real_presence,
            }
        )
    return result
