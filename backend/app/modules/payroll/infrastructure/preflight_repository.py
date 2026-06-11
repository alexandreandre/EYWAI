"""Persistance des résolutions et acquittements pré-paie."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_resolutions(
    company_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    res = (
        supabase.table("payroll_anomaly_resolutions")
        .select("*")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
    return res.data or []


def upsert_resolution(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
    status: str,
    motif: str,
    commentaire: Optional[str],
    resolved_by: str,
) -> Dict[str, Any]:
    payload = {
        "company_id": company_id,
        "employee_id": employee_id,
        "year": year,
        "month": month,
        "anomaly_type": anomaly_type,
        "status": status,
        "motif": motif,
        "commentaire": commentaire,
        "resolved_by": resolved_by,
        "resolved_at": _now_iso(),
    }
    res = (
        supabase.table("payroll_anomaly_resolutions")
        .upsert(payload, on_conflict="company_id,employee_id,year,month,anomaly_type")
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else payload


def delete_resolution(
    *,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    anomaly_type: str,
) -> None:
    (
        supabase.table("payroll_anomaly_resolutions")
        .delete()
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("anomaly_type", anomaly_type)
        .execute()
    )


def insert_acknowledgement(
    *,
    company_id: str,
    year: int,
    month: int,
    open_anomalies_count: int,
    anomaly_types_summary: List[str],
    commentaire: Optional[str],
    acknowledged_by: str,
) -> Dict[str, Any]:
    payload = {
        "company_id": company_id,
        "year": year,
        "month": month,
        "open_anomalies_count": open_anomalies_count,
        "anomaly_types_summary": anomaly_types_summary,
        "commentaire": commentaire,
        "acknowledged_by": acknowledged_by,
        "acknowledged_at": _now_iso(),
    }
    res = supabase.table("payroll_preflight_acknowledgements").insert(payload).execute()
    rows = res.data or []
    return rows[0] if rows else payload
