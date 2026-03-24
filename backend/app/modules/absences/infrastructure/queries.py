"""
Requêtes de lecture — employees, employee_schedules, repos_compensateur_credits, salary_certificates.

Pas de logique métier : uniquement lecture Supabase. Comportement identique à l'ancien routeur.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.database import supabase

BUCKET_SALARY_CERTIFICATES = "salary_certificates"


def resolve_employee_id_for_user(user_id: str) -> Optional[str]:
    """
    Résout l'ID employé à partir de l'ID utilisateur.
    Priorité : employees.id = user_id puis employees.user_id = user_id.
    """
    emp = (
        supabase.table("employees")
        .select("id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if emp.data:
        return emp.data["id"]
    emp2 = (
        supabase.table("employees")
        .select("id")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    return emp2.data["id"] if emp2.data else None


def get_employee_hire_date(employee_id: str) -> Optional[str]:
    """Retourne hire_date (iso) pour un employé."""
    r = (
        supabase.table("employees")
        .select("hire_date")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return r.data.get("hire_date") if r.data else None


def get_employee_company_id(employee_id: str) -> Optional[str]:
    """Retourne company_id pour un employé."""
    r = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    return r.data.get("company_id") if r.data else None


def get_employees_hire_dates_batch(
    employee_ids: List[str],
) -> Dict[str, date]:
    """Retourne un mapping employee_id -> hire_date (date) pour une liste d'employés."""
    if not employee_ids:
        return {}
    r = (
        supabase.table("employees")
        .select("id", "hire_date")
        .in_("id", employee_ids)
        .execute()
    )
    result = {}
    for row in r.data or []:
        if row.get("hire_date"):
            h = row["hire_date"]
            result[row["id"]] = (
                date.fromisoformat(h) if isinstance(h, str) else h
            )
    return result


def get_repos_credits_by_employee_year(
    employee_ids: List[str], year: int
) -> Dict[str, float]:
    """Somme des jours repos_compensateur_credits par employee_id pour l'année."""
    if not employee_ids:
        return {}
    credits_resp = (
        supabase.table("repos_compensateur_credits")
        .select("employee_id", "jours")
        .in_("employee_id", employee_ids)
        .eq("year", year)
        .execute()
    )
    result: Dict[str, float] = {}
    for c in credits_resp.data or []:
        eid = c.get("employee_id")
        result[eid] = result.get(eid, 0.0) + float(c.get("jours", 0) or 0)
    return result


def get_planned_calendar(
    employee_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    """Retourne planned_calendar.calendrier_prevu pour un mois."""
    response = (
        supabase.table("employee_schedules")
        .select("planned_calendar")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    if response.data and response.data.get("planned_calendar"):
        return response.data["planned_calendar"].get("calendrier_prevu", [])
    return []


def get_salary_certificate_record(
    absence_request_id: str,
) -> Optional[Dict[str, Any]]:
    """Enregistrement salary_certificates pour une absence (storage_path, filename, etc.)."""
    r = (
        supabase.table("salary_certificates")
        .select("*")
        .eq("absence_request_id", absence_request_id)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def list_absence_requests_validated_for_cp(
    employee_id: str, exclude_request_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Demandes validées de type conge_paye pour un employé (pour calcul jours_payes)."""
    query = (
        supabase.table("absence_requests")
        .select("selected_days", "jours_payes")
        .eq("employee_id", employee_id)
        .eq("type", "conge_paye")
        .eq("status", "validated")
    )
    if exclude_request_id:
        query = query.neq("id", exclude_request_id)
    result = query.execute()
    return result.data or []
