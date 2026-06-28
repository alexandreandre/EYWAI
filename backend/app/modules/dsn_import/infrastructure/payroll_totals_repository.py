"""Persistance des totaux paie DSN agrégés par entreprise et période."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin_client
from app.core.logging import get_logger

logger = get_logger("modules.dsn_import.payroll_totals_repository")

TABLE = "company_dsn_payroll_totals"
_MIGRATION = "supabase/migrations/20260625150000_company_dsn_payroll_totals.sql"
_SCHEMA_MISSING_LOGGED = False


def _is_schema_missing(exc: Exception) -> bool:
    msg = str(exc)
    return "PGRST205" in msg or "Could not find the table" in msg


def _log_schema_missing_once(context: str) -> None:
    global _SCHEMA_MISSING_LOGGED
    if _SCHEMA_MISSING_LOGGED:
        return
    _SCHEMA_MISSING_LOGGED = True
    logger.warning(
        "%s : table %s absente — appliquer la migration %s",
        context,
        TABLE,
        _MIGRATION,
    )


def upsert_totals(
    company_id: str,
    period: str,
    *,
    gross_salary: float,
    net_imposable: float,
    pas: float,
    employee_count: int,
    employees_with_gross: int,
    employee_charges: float = 0.0,
    employer_charges: float = 0.0,
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
        "employee_charges": round(float(employee_charges), 2),
        "employer_charges": round(float(employer_charges), 2),
        "employee_count": int(employee_count),
        "employees_with_gross": int(employees_with_gross),
        "last_batch_id": last_batch_id,
        "updated_at": now,
    }
    try:
        client.table(TABLE).upsert(row, on_conflict="company_id,period").execute()
    except APIError as exc:
        if _is_schema_missing(exc):
            _log_schema_missing_once("upsert_totals")
            return
        raise


def delete_period(company_id: str, period: str) -> None:
    client = get_supabase_admin_client()
    try:
        (
            client.table(TABLE)
            .delete()
            .eq("company_id", company_id)
            .eq("period", period)
            .execute()
        )
    except APIError as exc:
        if _is_schema_missing(exc):
            _log_schema_missing_once("delete_period")
            return
        raise


def list_by_company(company_id: str, *, limit: int = 36) -> List[Dict[str, Any]]:
    client = get_supabase_admin_client()
    try:
        resp = (
            client.table(TABLE)
            .select("*")
            .eq("company_id", company_id)
            .order("period", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []
    except APIError as exc:
        if _is_schema_missing(exc):
            _log_schema_missing_once("list_by_company")
            return []
        raise


def list_by_companies(
    company_ids: List[str], *, limit_per_company: int = 36
) -> List[Dict[str, Any]]:
    if not company_ids:
        return []
    client = get_supabase_admin_client()
    try:
        resp = (
            client.table(TABLE)
            .select("*")
            .in_("company_id", company_ids)
            .order("period", desc=True)
            .execute()
        )
        rows = resp.data or []
        if limit_per_company <= 0:
            return rows
        counts: Dict[str, int] = {}
        kept: List[Dict[str, Any]] = []
        for row in rows:
            cid = str(row.get("company_id") or "")
            n = counts.get(cid, 0)
            if n >= limit_per_company:
                continue
            counts[cid] = n + 1
            kept.append(row)
        return kept
    except APIError as exc:
        if _is_schema_missing(exc):
            _log_schema_missing_once("list_by_companies")
            return []
        raise


def get_period(company_id: str, period: str) -> Optional[Dict[str, Any]]:
    client = get_supabase_admin_client()
    try:
        resp = (
            client.table(TABLE)
            .select("*")
            .eq("company_id", company_id)
            .eq("period", period)
            .maybe_single()
            .execute()
        )
        return resp.data if resp and resp.data else None
    except APIError as exc:
        if _is_schema_missing(exc):
            _log_schema_missing_once("get_period")
            return None
        raise
