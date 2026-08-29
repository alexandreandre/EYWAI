"""
Requêtes de lecture transverses (companies, employees) pour le module repos_compensateur.

Pas de logique métier : lecture Supabase uniquement. Comportement identique au service actuel.
"""

from __future__ import annotations

from app.core.database import supabase


def get_company_effectif(company_id: str) -> int | None:
    """Récupère l'effectif de l'entreprise (pour taux COR)."""
    resp = (
        supabase.table("companies")
        .select("effectif")
        .eq("id", company_id)
        .single()
        .execute()
    )
    if not resp.data:
        return None
    val = resp.data.get("effectif")
    return int(val) if val is not None else None


def get_employees_for_company(company_id: str) -> list[dict]:
    """Liste des employés actifs de l'entreprise."""
    resp = (
        supabase.table("employees")
        .select(
            "id, company_id, first_name, last_name, hire_date, duree_hebdomadaire, employment_status"
        )
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []


def get_validated_repos_requests(
    company_id: str, employee_ids: list[str]
) -> dict[str, list[dict]]:
    """Demandes repos_compensateur validées par employé."""
    if not employee_ids:
        return {}
    resp = (
        supabase.table("absence_requests")
        .select("employee_id, type, status, selected_days")
        .eq("company_id", company_id)
        .eq("type", "repos_compensateur")
        .eq("status", "validated")
        .in_("employee_id", employee_ids)
        .execute()
    )
    result: dict[str, list[dict]] = {}
    for row in resp.data or []:
        eid = str(row["employee_id"])
        result.setdefault(eid, []).append(row)
    return result
