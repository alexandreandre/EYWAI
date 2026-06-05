# app/modules/cse/infrastructure/delegation_queries.py
"""
Requêtes Supabase — heures de délégation conformes (config, transfers, requests, paie).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase


def fetch_delegation_config(company_id: str) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("cse_delegation_config")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def upsert_delegation_config_row(
    company_id: str,
    reference_headcount: int,
    reference_date: date,
    report_enabled: bool,
    mutualisation_enabled: bool,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    existing = fetch_delegation_config(company_id)
    payload = {
        "company_id": company_id,
        "reference_headcount": reference_headcount,
        "reference_date": reference_date.isoformat(),
        "report_enabled": report_enabled,
        "mutualisation_enabled": mutualisation_enabled,
    }
    if existing:
        response = (
            supabase.table("cse_delegation_config")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        if created_by:
            payload["created_by"] = created_by
        response = supabase.table("cse_delegation_config").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Erreur lors de la sauvegarde de la configuration délégation")
    return response.data[0]


def fetch_active_mandate_with_override(
    company_id: str, employee_id: str
) -> Optional[Dict[str, Any]]:
    response = (
        supabase.table("cse_elected_members")
        .select(
            "id, employee_id, role, monthly_hours_override, start_date, end_date, is_active"
        )
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("is_active", True)
        .gte("end_date", date.today().isoformat())
        .order("end_date", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_delegation_hours_raw(
    company_id: str,
    employee_id: str,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("cse_delegation_hours")
        .select("*")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
    )
    if period_start:
        query = query.gte("date", period_start.isoformat())
    if period_end:
        query = query.lte("date", period_end.isoformat())
    response = query.order("date", desc=True).execute()
    return response.data or []


def fetch_delegation_transfers(
    company_id: str,
    employee_id: Optional[str] = None,
    period_start: Optional[Tuple[int, int]] = None,
    period_end: Optional[Tuple[int, int]] = None,
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("cse_delegation_transfers")
        .select("*")
        .eq("company_id", company_id)
    )
    if employee_id:
        query = query.or_(
            f"from_employee_id.eq.{employee_id},to_employee_id.eq.{employee_id}"
        )
    response = query.execute()
    rows = response.data or []
    if period_start or period_end:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            key = (int(row["period_year"]), int(row["period_month"]))
            if period_start and key < period_start:
                continue
            if period_end and key > period_end:
                continue
            filtered.append(row)
        return filtered
    return rows


def insert_delegation_transfer(row: Dict[str, Any]) -> Dict[str, Any]:
    response = supabase.table("cse_delegation_transfers").insert(row).execute()
    if not response.data:
        raise RuntimeError("Erreur lors de la création de la mutualisation")
    return response.data[0]


def fetch_delegation_requests(
    company_id: str,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("cse_delegation_requests")
        .select("*")
        .eq("company_id", company_id)
    )
    if employee_id:
        query = query.eq("employee_id", employee_id)
    if status:
        query = query.eq("status", status)
    response = query.order("planned_date", desc=True).execute()
    return response.data or []


def insert_delegation_request(row: Dict[str, Any]) -> Dict[str, Any]:
    response = supabase.table("cse_delegation_requests").insert(row).execute()
    if not response.data:
        raise RuntimeError("Erreur lors de la création du bon de délégation")
    return response.data[0]


def update_delegation_request(request_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    response = (
        supabase.table("cse_delegation_requests")
        .update(updates)
        .eq("id", request_id)
        .execute()
    )
    if not response.data:
        raise RuntimeError("Bon de délégation introuvable")
    return response.data[0]


def insert_payroll_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    response = supabase.table("cse_delegation_payroll_entries").insert(row).execute()
    if not response.data:
        raise RuntimeError("Erreur lors de l'imputation paie délégation")
    return response.data[0]


def fetch_payroll_entries(
    company_id: str, year: int, month: int, employee_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("cse_delegation_payroll_entries")
        .select("*")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
    )
    if employee_id:
        query = query.eq("employee_id", employee_id)
    response = query.execute()
    return response.data or []


def count_active_employees(company_id: str) -> int:
    """Effectif actif pour pré-remplir la config (fallback si non configurée)."""
    response = (
        supabase.table("employees")
        .select("id, employment_status")
        .eq("company_id", company_id)
        .execute()
    )
    employees = response.data or []
    active = [
        e
        for e in employees
        if str(e.get("employment_status") or "actif").lower()
        in ("actif", "active", "")
    ]
    return len(active) if active else len(employees)


def _parse_date_value(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    raise ValueError(f"Date invalide: {value}")
