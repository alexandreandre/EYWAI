"""Repository périodes de référence horaire."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.core.database import supabase


def list_periods(company_id: str, *, active_only: bool = True) -> list[dict[str, Any]]:
    q = (
        supabase.table("company_work_time_periods")
        .select("*")
        .eq("company_id", company_id)
        .order("start_date")
    )
    if active_only:
        q = q.eq("is_active", True)
    resp = q.execute()
    return resp.data or []


def get_period(company_id: str, period_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_work_time_periods")
        .select("*")
        .eq("company_id", company_id)
        .eq("id", period_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_period(company_id: str, data: dict[str, Any], period_id: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {**data, "company_id": company_id, "updated_at": now}
    if "start_date" in payload and hasattr(payload["start_date"], "isoformat"):
        payload["start_date"] = payload["start_date"].isoformat()
    if "end_date" in payload and hasattr(payload.get("end_date"), "isoformat"):
        payload["end_date"] = payload["end_date"].isoformat()
    if period_id:
        resp = (
            supabase.table("company_work_time_periods")
            .update(payload)
            .eq("id", period_id)
            .eq("company_id", company_id)
            .execute()
        )
        return (resp.data or [{}])[0]
    payload.setdefault("created_at", now)
    resp = supabase.table("company_work_time_periods").insert(payload).execute()
    return (resp.data or [payload])[0]


def soft_delete_period(company_id: str, period_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (
        supabase.table("company_work_time_periods")
        .update({"is_active": False, "updated_at": now})
        .eq("id", period_id)
        .eq("company_id", company_id)
        .execute()
    )


def list_active_payroll_periods(company_id: str, ref_date: date | None = None) -> list[dict[str, Any]]:
    rows = list_periods(company_id, active_only=True)
    if ref_date is None:
        return [r for r in rows if r.get("affects_payroll")]
    out = []
    for row in rows:
        if not row.get("affects_payroll"):
            continue
        start = date.fromisoformat(str(row["start_date"])[:10])
        end_raw = row.get("end_date")
        end = date.fromisoformat(str(end_raw)[:10]) if end_raw else None
        if start <= ref_date and (end is None or ref_date <= end):
            out.append(row)
    return out
