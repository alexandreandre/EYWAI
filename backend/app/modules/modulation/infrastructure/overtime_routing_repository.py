"""Repository décisions routage HS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase


def get_decision(employee_id: str, year: int, month: int) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_overtime_routing_decisions")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_decision(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {**data, "updated_at": now}
    existing = get_decision(
        str(data["employee_id"]), int(data["year"]), int(data["month"])
    )
    if existing:
        resp = (
            supabase.table("employee_overtime_routing_decisions")
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
        return (resp.data or [existing])[0]
    payload.setdefault("created_at", now)
    resp = (
        supabase.table("employee_overtime_routing_decisions")
        .insert(payload)
        .execute()
    )
    return (resp.data or [payload])[0]


def list_for_period(
    company_id: str, year: int, month: int, *, status: str | None = None
) -> list[dict[str, Any]]:
    q = (
        supabase.table("employee_overtime_routing_decisions")
        .select("*")
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
    )
    if status:
        q = q.eq("status", status)
    resp = q.execute()
    return resp.data or []


def mark_applied_payroll(employee_id: str, year: int, month: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (
        supabase.table("employee_overtime_routing_decisions")
        .update({"status": "applied_payroll", "updated_at": now})
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .execute()
    )
