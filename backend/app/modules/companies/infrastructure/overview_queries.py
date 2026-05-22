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
            "id, contract_type, hire_date, job_title, statut, date_naissance, "
            "birth_date, contract_end_date, weekly_hours, duree_hebdomadaire, "
            "employment_status, status, sexe, gender, genre"
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

    return {
        "employees": employees,
        "exits": exits,
        "absences": absences,
        "mutuelle_employee_ids": mutuelle_ids,
    }
