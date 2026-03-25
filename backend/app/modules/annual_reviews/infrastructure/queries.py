"""
Requêtes Supabase pour annual_reviews (exécution DB).

Pas de logique métier : uniquement construction et exécution des appels Supabase.
Le repository utilise ces fonctions. Comportement identique au legacy.
"""

from typing import Any, Dict, List, Optional

from app.core.database import supabase


def query_list_by_company(
    company_id: str,
    year: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste les entretiens de l'entreprise avec jointure employees (first_name, last_name, job_title)."""
    q = (
        supabase.table("annual_reviews")
        .select(
            "id, employee_id, company_id, year, status, planned_date, completed_date, created_at, "
            "employees(first_name, last_name, job_title)"
        )
        .eq("company_id", company_id)
        .order("year", desc=True)
        .order("created_at", desc=True)
    )
    if year is not None:
        q = q.eq("year", year)
    if status is not None:
        q = q.eq("status", status)
    resp = q.execute()
    return list(resp.data or [])


def query_get_by_id(review_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un entretien par id."""
    resp = (
        supabase.table("annual_reviews")
        .select("*")
        .eq("id", review_id)
        .single()
        .execute()
    )
    return resp.data if resp.data else None


def query_list_by_employee(employee_id: str, company_id: str) -> List[Dict[str, Any]]:
    """Liste les entretiens d'un employé pour une entreprise."""
    resp = (
        supabase.table("annual_reviews")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .order("year", desc=True)
        .execute()
    )
    return list(resp.data or [])


def query_get_my_current(
    employee_id: str, company_id: str, year: int
) -> Optional[Dict[str, Any]]:
    """Entretien d'un employé pour une année donnée (ex. année courante)."""
    resp = (
        supabase.table("annual_reviews")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("company_id", company_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    if not resp.data or len(resp.data) == 0:
        return None
    return dict(resp.data[0])


def query_insert(data: Dict[str, Any]) -> Dict[str, Any]:
    """Insère un entretien et retourne la ligne créée (avec id)."""
    resp = supabase.table("annual_reviews").insert(data).execute()
    if not resp.data or len(resp.data) == 0:
        raise RuntimeError("Erreur lors de la création.")
    new_id = resp.data[0]["id"]
    full = (
        supabase.table("annual_reviews").select("*").eq("id", new_id).single().execute()
    )
    if not full.data:
        raise RuntimeError("Erreur lors de la récupération de l'entretien créé.")
    return dict(full.data)


def query_update(review_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Met à jour un entretien et retourne la ligne mise à jour."""
    upd = supabase.table("annual_reviews").update(data).eq("id", review_id).execute()
    if not upd.data or len(upd.data) == 0:
        return None
    full = (
        supabase.table("annual_reviews")
        .select("*")
        .eq("id", review_id)
        .single()
        .execute()
    )
    return dict(full.data) if full.data else None


def query_delete(review_id: str) -> None:
    """Supprime un entretien."""
    supabase.table("annual_reviews").delete().eq("id", review_id).execute()


def query_employee_company_id(employee_id: str) -> Optional[str]:
    """Retourne le company_id d'un employé."""
    resp = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    if not resp.data:
        return None
    return resp.data.get("company_id")


def query_employee_by_id(employee_id: str) -> Optional[Dict[str, Any]]:
    """Retourne les champs employé pour le PDF (id, first_name, last_name, job_title)."""
    resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, job_title")
        .eq("id", employee_id)
        .single()
        .execute()
    )
    return dict(resp.data) if resp.data else None


def query_company_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    """Retourne les données entreprise (pour PDF)."""
    resp = (
        supabase.table("companies").select("*").eq("id", company_id).single().execute()
    )
    return dict(resp.data) if resp.data else None
