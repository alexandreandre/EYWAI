"""
Providers infrastructure : données bulletins pour le calcul HS/COR.

Implémente IPayslipDataProvider. Lecture table payslips (payslip_data).
Comportement identique au service actuel (groupement par employé puis par mois).
"""

from __future__ import annotations

from typing import Any

from app.core.database import supabase


def get_bulletins_par_mois_par_employe(
    company_id: str, year: int, employee_ids: list[str]
) -> dict[str, dict[int, dict[str, Any]]]:
    """
    Pour chaque employee_id, retourne un dict { month: payslip_data }.
    Source : table payslips (employee_id, month, payslip_data).
    """
    if not employee_ids:
        return {}
    payslips_resp = (
        supabase.table("payslips")
        .select("employee_id, month, payslip_data")
        .eq("company_id", company_id)
        .eq("year", year)
        .in_("employee_id", employee_ids)
        .execute()
    )
    payslips = payslips_resp.data or []
    result: dict[str, dict[int, dict[str, Any]]] = {}
    for ps in payslips:
        emp_id = ps["employee_id"]
        m = ps["month"]
        if emp_id not in result:
            result[emp_id] = {}
        result[emp_id][m] = ps.get("payslip_data") or {}
    return result
