"""Chargement effectifs et config OETH."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.core.database import supabase
from app.modules.oeth_settings.domain.constants import DEFAULT_OETH_CONFIG
from app.modules.oeth_settings.infrastructure.boeth_repository import (
    boeth_profiles_repository,
)


def load_oeth_config() -> dict:
    r = (
        supabase.table("payroll_config")
        .select("config_data")
        .eq("config_key", "oeth")
        .eq("is_active", True)
        .is_("company_id", "null")
        .maybe_single()
        .execute()
    )
    if r and r.data and isinstance(r.data.get("config_data"), dict):
        merged = {**DEFAULT_OETH_CONFIG, **r.data["config_data"]}
        return merged
    return dict(DEFAULT_OETH_CONFIG)


def load_smic_horaire(year: int) -> float:
    r = (
        supabase.table("payroll_config")
        .select("config_data")
        .eq("config_key", "smic")
        .eq("is_active", True)
        .is_("company_id", "null")
        .maybe_single()
        .execute()
    )
    if r and r.data:
        data = r.data.get("config_data") or {}
        horaire = data.get("horaire") or data.get("smic_horaire")
        if horaire:
            return float(horaire)
    return 11.88 if year >= 2025 else 11.65


def load_employees_for_oeth(company_id: str) -> List[Dict[str, Any]]:
    r = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, hire_date, end_date, date_naissance, "
            "contract_type, status, job_code, pcs_code"
        )
        .eq("company_id", company_id)
        .neq("status", "parti")
        .execute()
    )
    employees = r.data or []
    profiles = {
        p["employee_id"]: p
        for p in boeth_profiles_repository.get_active_by_company(company_id)
    }
    for emp in employees:
        prof = profiles.get(emp["id"])
        emp["boeth"] = prof or {}
    return employees


def count_active_employees(company_id: str) -> int:
    r = (
        supabase.table("employees")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .neq("status", "parti")
        .execute()
    )
    return r.count or 0


def ecap_job_codes(company_id: str, year: int) -> Set[str]:
    from app.modules.oeth_settings.infrastructure.boeth_repository import (
        oeth_annual_repository,
    )

    rows = oeth_annual_repository.list_ecap(company_id, year)
    return {str(r.get("job_code_pcs_ese")) for r in rows if r.get("job_code_pcs_ese")}
