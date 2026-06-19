"""
Lecture agrégée pour GET /api/company/overview.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from app.core.database import supabase


def fetch_overview_raw(company_id: str) -> Dict[str, Any]:
    """Charge employés, sorties, absences et couverture mutuelle."""
    employees_res = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, contract_type, hire_date, job_title, statut, "
            "date_naissance, contract_end_date, weekly_hours, "
            "duree_hebdomadaire, employment_status, status, sexe, gender, genre, "
            "collective_agreement_id, specificites_paie"
        )
        .eq("company_id", company_id)
        .execute()
    )
    employees = employees_res.data or []

    exits_res = (
        supabase.table("employee_exits")
        .select("id, exit_date, departure_date, created_at, employee_id")
        .eq("company_id", company_id)
        .execute()
    )
    exits = exits_res.data or []

    absences_res = (
        supabase.table("absence_requests")
        .select("employee_id, type, selected_days, status")
        .eq("status", "validated")
        .eq("company_id", company_id)
        .execute()
    )
    absences = absences_res.data or []

    mutuelle_ids: Set[str] = set()
    try:
        links = (
            supabase.table("employee_mutuelle_types")
            .select("employee_id")
            .eq("company_id", company_id)
            .execute()
        )
        for row in links.data or []:
            if row.get("employee_id"):
                mutuelle_ids.add(str(row["employee_id"]))
    except Exception:
        pass

    company_cc_ids: Set[str] = set()
    try:
        cc_res = (
            supabase.table("company_collective_agreements")
            .select("collective_agreement_id")
            .eq("company_id", company_id)
            .execute()
        )
        for row in cc_res.data or []:
            cc_id = row.get("collective_agreement_id")
            if cc_id:
                company_cc_ids.add(str(cc_id))
    except Exception:
        pass

    jei_settings: Dict[str, Any] | None = None
    try:
        jei_res = (
            supabase.table("company_jei_settings")
            .select("jei_enabled, date_creation_etablissement")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        jei_settings = jei_res.data if jei_res else None
    except Exception:
        jei_settings = None

    return {
        "employees": employees,
        "exits": exits,
        "absences": absences,
        "mutuelle_employee_ids": mutuelle_ids,
        "company_cc_ids": company_cc_ids,
        "jei_settings": jei_settings,
    }
