"""Repository CP ancienneté."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    FORFAIT_ANNUAL_DAYS_DEFAULT,
    PLASTURGIE_0292_RULES,
    parse_cp_seniority_rules,
)

_VALID_PRESETS = frozenset(
    {"plasturgie_idcc_0292", "lewis_agreement", "metallurgie_idcc_3248", "custom"}
)


def _row_to_settings(row: dict[str, Any]) -> CpSenioritySettings:
    rules_raw = row.get("rules") or {}
    if isinstance(rules_raw, str):
        import json

        rules_raw = json.loads(rules_raw)
    preset = row.get("preset") or "plasturgie_idcc_0292"
    if preset not in _VALID_PRESETS:
        preset = "plasturgie_idcc_0292"
    basis = row.get("seniority_basis") or "company_only"
    if basis not in (
        "company_only",
        "include_prior_service",
        "seniority_reference_date",
    ):
        basis = "company_only"
    unit = row.get("counting_unit") or "ouvrable"
    if unit not in ("ouvrable", "ouvre"):
        unit = "ouvrable"
    return CpSenioritySettings(
        enabled=bool(row.get("enabled")),
        preset=preset,
        seniority_reference=row.get("seniority_reference") or "cp_period_end",
        seniority_basis=basis,
        counting_unit=unit,
        rules=parse_cp_seniority_rules(rules_raw if preset == "custom" else None),
        forfait_annual_days_default=float(
            row.get("forfait_annual_days_default") or FORFAIT_ANNUAL_DAYS_DEFAULT
        ),
        forfait_reduction_enabled=bool(
            row.get("forfait_reduction_enabled", True)
        ),
        company_agreement_overrides=bool(row.get("company_agreement_overrides")),
    )


def get_cp_seniority_settings_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_cp_seniority_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def get_cp_seniority_settings(company_id: str) -> CpSenioritySettings:
    row = get_cp_seniority_settings_row(company_id)
    if not row:
        return CpSenioritySettings.plasturgie_default()
    return _row_to_settings(row)


def upsert_cp_seniority_settings(
    company_id: str, payload: dict[str, Any]
) -> CpSenioritySettings:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {"company_id": company_id, "updated_at": now}
    allowed = (
        "enabled",
        "preset",
        "seniority_reference",
        "seniority_basis",
        "counting_unit",
        "rules",
        "forfait_annual_days_default",
        "forfait_reduction_enabled",
        "company_agreement_overrides",
    )
    for key in allowed:
        if key in payload:
            row[key] = payload[key]

    existing = get_cp_seniority_settings_row(company_id)
    if existing:
        supabase.table("company_cp_seniority_settings").update(row).eq(
            "company_id", company_id
        ).execute()
    else:
        row["created_at"] = now
        if "rules" not in row:
            row["rules"] = PLASTURGIE_0292_RULES
        supabase.table("company_cp_seniority_settings").insert(row).execute()
    return get_cp_seniority_settings(company_id)


def get_cp_seniority_grant(employee_id: str, grant_year: int) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_cp_seniority_grants")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("grant_year", grant_year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_cp_seniority_grant(
    company_id: str,
    employee_id: str,
    grant_year: int,
    days_granted: float,
    category_resolved: str | None,
    seniority_years_at_ref: float,
    forfait_days_reduction: float,
    calculation_snapshot: dict[str, Any],
    *,
    status: str = "computed",
    validated_by: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_cp_seniority_grant(employee_id, grant_year)
    row = {
        "company_id": company_id,
        "employee_id": employee_id,
        "grant_year": grant_year,
        "days_granted": days_granted,
        "category_resolved": category_resolved,
        "seniority_years_at_ref": seniority_years_at_ref,
        "forfait_days_reduction": forfait_days_reduction,
        "calculation_snapshot": calculation_snapshot,
        "status": status,
        "updated_at": now,
    }
    if status in ("validated", "overridden"):
        row["validated_at"] = now
        if validated_by:
            row["validated_by"] = validated_by
    if existing:
        supabase.table("employee_cp_seniority_grants").update(row).eq(
            "id", existing["id"]
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("employee_cp_seniority_grants").insert(row).execute()
    result = get_cp_seniority_grant(employee_id, grant_year)
    return result or row


def validate_cp_seniority_grant(
    company_id: str,
    employee_id: str,
    grant_year: int,
    *,
    status: str = "validated",
    validated_by: str | None = None,
) -> dict[str, Any] | None:
    existing = get_cp_seniority_grant(employee_id, grant_year)
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "status": status,
        "validated_at": now,
        "updated_at": now,
    }
    if validated_by:
        row["validated_by"] = validated_by
    supabase.table("employee_cp_seniority_grants").update(row).eq(
        "id", existing["id"]
    ).execute()
    return get_cp_seniority_grant(employee_id, grant_year)


def list_cp_seniority_grants_for_company(
    company_id: str, grant_year: int
) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_cp_seniority_grants")
        .select("*")
        .eq("company_id", company_id)
        .eq("grant_year", grant_year)
        .execute()
    )
    return list(resp.data or [])
