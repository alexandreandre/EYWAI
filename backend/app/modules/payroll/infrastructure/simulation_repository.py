"""
Accès Supabase pour les simulations de paie (payroll_simulations, payroll_config, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase


def fetch_company_row(company_id: str) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("companies")
        .select("*")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    return response.data


def fetch_employee_row(employee_id: str) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return response.data


def fetch_active_payroll_config_rows() -> List[Dict[str, Any]]:
    response = (
        supabase.table("payroll_config")
        .select("config_key, config_data")
        .eq("is_active", True)
        .execute()
    )
    return response.data or []


def fetch_simulation_row(
    simulation_id: str, company_id: str
) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("payroll_simulations")
        .select("*")
        .eq("id", simulation_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return response.data


def insert_simulation_row(payload: Dict[str, Any]) -> Optional[str]:
    response = supabase.table("payroll_simulations").insert(payload).execute()
    if not response.data:
        return None
    return str(response.data[0].get("id") or "")


def list_simulation_rows(
    company_id: str,
    employee_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("payroll_simulations")
        .select(
            "id, employee_id, month, year, simulation_type, scenario_name, payslip_data, created_at"
        )
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .order("created_at", desc=True)
    )
    if month is not None:
        query = query.eq("month", month)
    if year is not None:
        query = query.eq("year", year)
    return query.execute().data or []


def fetch_payslip_row(
    payslip_id: str, company_id: str
) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("payslips")
        .select("id, company_id, payslip_data")
        .eq("id", payslip_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return response.data


def delete_simulation_row(simulation_id: str, company_id: str) -> None:
    supabase.table("payroll_simulations").delete().eq("id", simulation_id).eq(
        "company_id", company_id
    ).execute()
