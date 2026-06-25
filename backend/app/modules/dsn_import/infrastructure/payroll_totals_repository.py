"""Persistance des totaux paie DSN agrégés par entreprise et période."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_admin_client

TABLE = "company_dsn_payroll_totals"


def upsert_totals(
    company_id: str,
    period: str,
    *,
    gross_salary: float,
    net_imposable: float,
    pas: float,
    employee_count: int,
    employees_with_gross: int,
    last_batch_id: Optional[str] = None,
) -> None:
    client = get_supabase_admin_client()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "company_id": company_id,
        "period": period,
        "gross_salary": round(float(gross_salary), 2),
        "net_imposable": round(float(net_imposable), 2),
        "pas": round(float(pas), 2),
        "employee_count": int(employee_count),
        "employees_with_gross": int(employees_with_gross),
        "last_batch_id": last_batch_id,
        "updated_at": now,
    }
    client.table(TABLE).upsert(row, on_conflict="company_id,period").execute()


def delete_period(company_id: str, period: str) -> None:
    client = get_supabase_admin_client()
    (
        client.table(TABLE)
        .delete()
        .eq("company_id", company_id)
        .eq("period", period)
        .execute()
    )


def list_by_company(company_id: str, *, limit: int = 36) -> List[Dict[str, Any]]:
    client = get_supabase_admin_client()
    resp = (
        client.table(TABLE)
        .select("*")
        .eq("company_id", company_id)
        .order("period", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def get_period(company_id: str, period: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    resp = (
        client.table(TABLE)
        .select("*")
        .eq("company_id", company_id)
        .eq("period", period)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None
