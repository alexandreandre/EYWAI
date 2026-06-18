"""Repository fractionnement CP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.fractionnement import (
    FIFTH_WEEK_DEDUCTION_OUVRES_DEFAULT,
    OUVRES_TO_OUVRABLES_DEFAULT,
)


def get_fractionnement_settings_row(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("company_cp_fractionnement_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return {
            "company_id": company_id,
            "fractionnement_enabled": False,
            "cp_unit": "ouvres",
            "ouvres_to_ouvrables_ratio": OUVRES_TO_OUVRABLES_DEFAULT,
            "fifth_week_deduction_ouvres": FIFTH_WEEK_DEDUCTION_OUVRES_DEFAULT,
        }
    return rows[0]


def is_fractionnement_enabled(company_id: str) -> bool:
    return bool(get_fractionnement_settings_row(company_id).get("fractionnement_enabled"))


def upsert_fractionnement_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {"company_id": company_id, "updated_at": now}
    allowed = (
        "fractionnement_enabled",
        "cp_unit",
        "ouvres_to_ouvrables_ratio",
        "fifth_week_deduction_ouvres",
    )
    for key in allowed:
        if key in payload:
            row[key] = payload[key]

    existing = (
        supabase.table("company_cp_fractionnement_settings")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        supabase.table("company_cp_fractionnement_settings").update(row).eq(
            "company_id", company_id
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("company_cp_fractionnement_settings").insert(row).execute()
    return get_fractionnement_settings_row(company_id)


def get_fractionnement_input(
    company_id: str, employee_id: str, grant_year: int
) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_cp_fractionnement_inputs")
        .select("*")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("grant_year", grant_year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def list_fractionnement_inputs_for_company(
    company_id: str, grant_year: int
) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_cp_fractionnement_inputs")
        .select("*")
        .eq("company_id", company_id)
        .eq("grant_year", grant_year)
        .execute()
    )
    return list(resp.data or [])


def upsert_fractionnement_input(
    company_id: str,
    employee_id: str,
    grant_year: int,
    cp_reported_june_ouvres: float,
    cp_seniority_deduction_ouvres: float = 0.0,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_fractionnement_input(company_id, employee_id, grant_year)
    row = {
        "company_id": company_id,
        "employee_id": employee_id,
        "grant_year": grant_year,
        "cp_reported_june_ouvres": cp_reported_june_ouvres,
        "cp_seniority_deduction_ouvres": cp_seniority_deduction_ouvres,
        "updated_at": now,
    }
    if existing:
        supabase.table("employee_cp_fractionnement_inputs").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("employee_cp_fractionnement_inputs").insert(row).execute()
    result = get_fractionnement_input(company_id, employee_id, grant_year)
    return result or row


def get_fractionnement_grant(
    employee_id: str, grant_year: int
) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_cp_fractionnement_grants")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("grant_year", grant_year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_fractionnement_grant(
    company_id: str,
    employee_id: str,
    grant_year: int,
    payroll_year: int,
    payroll_month: int,
    days_granted: int,
    calculation_snapshot: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_fractionnement_grant(employee_id, grant_year)
    row = {
        "company_id": company_id,
        "employee_id": employee_id,
        "grant_year": grant_year,
        "payroll_year": payroll_year,
        "payroll_month": payroll_month,
        "days_granted": days_granted,
        "calculation_snapshot": calculation_snapshot,
        "updated_at": now,
    }
    if existing:
        supabase.table("employee_cp_fractionnement_grants").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("employee_cp_fractionnement_grants").insert(row).execute()
    result = get_fractionnement_grant(employee_id, grant_year)
    return result or row
