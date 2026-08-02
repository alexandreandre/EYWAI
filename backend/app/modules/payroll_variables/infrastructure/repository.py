"""Repository variables paie."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.core.database import supabase


def list_rules(company_id: str) -> list[dict[str, Any]]:
    resp = (
        supabase.table("company_payroll_variable_rules")
        .select("*")
        .eq("company_id", company_id)
        .order("sort_order")
        .execute()
    )
    return resp.data or []


def get_rule(company_id: str, rule_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_payroll_variable_rules")
        .select("*")
        .eq("company_id", company_id)
        .eq("id", rule_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_rule(company_id: str, data: dict[str, Any], rule_id: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row = {**data, "company_id": company_id, "updated_at": now}
    if rule_id:
        supabase.table("company_payroll_variable_rules").update(row).eq(
            "id", rule_id
        ).execute()
        return get_rule(company_id, rule_id) or row
    row["created_at"] = now
    resp = supabase.table("company_payroll_variable_rules").insert(row).execute()
    return (resp.data or [row])[0]


def delete_rule(company_id: str, rule_id: str) -> None:
    supabase.table("company_payroll_variable_rules").delete().eq(
        "company_id", company_id
    ).eq("id", rule_id).execute()


def find_existing_monthly_input(
    employee_id: str, year: int, month: int, name: str
) -> dict[str, Any] | None:
    resp = (
        supabase.table("monthly_inputs")
        # manual_override est indispensable : sans lui, la protection contre
        # l'écrasement d'une correction manuelle serait un no-op silencieux.
        .select("id, manual_override")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("name", name)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_monthly_input(row: dict[str, Any]) -> None:
    existing = find_existing_monthly_input(
        str(row["employee_id"]),
        int(row["year"]),
        int(row["month"]),
        str(row["name"]),
    )
    if existing:
        # Une ligne corrigée à la main fait autorité sur la génération : la RH a
        # tranché pour ce mois, on ne repasse pas derrière elle.
        if existing.get("manual_override"):
            return
        supabase.table("monthly_inputs").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        supabase.table("monthly_inputs").insert(row).execute()


def list_special_days(
    company_id: str, year: int, month: int
) -> list[dict[str, Any]]:
    import calendar

    _, last = calendar.monthrange(year, month)
    start = date(year, month, 1).isoformat()
    end = date(year, month, last).isoformat()
    resp = (
        supabase.table("company_payroll_special_days")
        .select("*")
        .eq("company_id", company_id)
        .gte("day_date", start)
        .lte("day_date", end)
        .execute()
    )
    return resp.data or []


def list_all_special_days(company_id: str, year: int | None = None) -> list[dict[str, Any]]:
    query = (
        supabase.table("company_payroll_special_days")
        .select("*")
        .eq("company_id", company_id)
        .order("day_date")
    )
    if year is not None:
        query = query.gte("day_date", f"{year}-01-01").lte("day_date", f"{year}-12-31")
    resp = query.execute()
    return resp.data or []


def create_special_day(company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    row = {**data, "company_id": company_id}
    resp = supabase.table("company_payroll_special_days").insert(row).execute()
    return (resp.data or [row])[0]


def delete_special_day(company_id: str, day_id: str) -> None:
    supabase.table("company_payroll_special_days").delete().eq(
        "company_id", company_id
    ).eq("id", day_id).execute()
