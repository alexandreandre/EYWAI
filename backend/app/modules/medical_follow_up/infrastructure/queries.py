# app/modules/medical_follow_up/infrastructure/queries.py
"""
Requêtes Supabase pour le suivi médical : obligations et employés.

Fonctions bas niveau prenant le client Supabase en argument.
Comportement identique au legacy (router / application).
"""

from typing import Any, Dict, List, Optional


def list_obligations_raw(
    supabase: Any,
    company_id: str,
    employee_id: Optional[str] = None,
    visit_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    due_from: Optional[str] = None,
    due_to: Optional[str] = None,
    with_employee_join: bool = True,
) -> List[Dict[str, Any]]:
    """Liste les obligations (hors annulées) avec filtres. Optionnel join employee(first_name, last_name)."""
    select = (
        "*, employee:employees(first_name, last_name)" if with_employee_join else "*"
    )
    query = (
        supabase.table("medical_follow_up_obligations")
        .select(select)
        .eq("company_id", company_id)
        .neq("status", "annulee")
    )
    if employee_id:
        query = query.eq("employee_id", employee_id)
    if visit_type:
        query = query.eq("visit_type", visit_type)
    if status:
        query = query.eq("status", status)
    if priority is not None:
        query = query.eq("priority", priority)
    if due_from:
        query = query.gte("due_date", due_from)
    if due_to:
        query = query.lte("due_date", due_to)
    query = query.order("priority").order("due_date")
    res = query.execute()
    return list(res.data or [])


def get_obligations_rows_for_kpis(
    supabase: Any, company_id: str
) -> List[Dict[str, Any]]:
    """Retourne les lignes (due_date, status, completed_date) pour le calcul des KPIs."""
    res = (
        supabase.table("medical_follow_up_obligations")
        .select("due_date, status, completed_date")
        .eq("company_id", company_id)
        .neq("status", "annulee")
        .execute()
    )
    return list(res.data or [])


def get_obligation_by_id(
    supabase: Any, obligation_id: str, company_id: str
) -> Optional[Dict[str, Any]]:
    """Retourne une obligation par id et company_id ou None."""
    res = (
        supabase.table("medical_follow_up_obligations")
        .select("id, company_id")
        .eq("id", obligation_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return res.data if res and res.data else None


def update_obligation_planified(
    supabase: Any,
    obligation_id: str,
    planned_date: str,
    justification: Optional[str],
) -> None:
    """Met à jour une obligation : status planifiée, planned_date, justification."""
    supabase.table("medical_follow_up_obligations").update(
        {
            "status": "planifiee",
            "planned_date": planned_date,
            "justification": justification,
        }
    ).eq("id", obligation_id).execute()


def update_obligation_completed(
    supabase: Any,
    obligation_id: str,
    completed_date: str,
    justification: Optional[str],
) -> None:
    """Met à jour une obligation : status réalisée, completed_date, justification."""
    supabase.table("medical_follow_up_obligations").update(
        {
            "status": "realisee",
            "completed_date": completed_date,
            "justification": justification,
        }
    ).eq("id", obligation_id).execute()


def insert_obligation(supabase: Any, payload: Dict[str, Any]) -> None:
    """Insère une obligation (visite à la demande ou autre)."""
    supabase.table("medical_follow_up_obligations").insert(payload).execute()


def get_employee_by_id(
    supabase: Any, employee_id: str, company_id: str
) -> Optional[Dict[str, Any]]:
    """Retourne l’employé par id et company_id ou None."""
    res = (
        supabase.table("employees")
        .select("id, company_id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return res.data if res and res.data else None


def get_employee_id_by_user_id(
    supabase: Any, user_id: str, company_id: str
) -> Optional[str]:
    """Retourne l’id employé pour un user_id et company_id ou None."""
    res = (
        supabase.table("employees")
        .select("id")
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return res.data.get("id") if res and res.data else None
