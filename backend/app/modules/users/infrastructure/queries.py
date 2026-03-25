"""
Requêtes métier complexes (lecture) pour le module users.

Exécution Supabase uniquement. Pas de règles métier ici.
Comportement identique aux requêtes inline des anciens routers.
"""

from typing import List, Optional

from app.core.database import supabase


def fetch_active_companies_with_groups() -> List[dict]:
    """Companies actives + company_groups (pour get_my_companies super_admin)."""
    r = (
        supabase.table("companies")
        .select(
            "id, company_name, siret, logo_url, logo_scale, group_id, company_groups(group_name, logo_url, logo_scale)"
        )
        .eq("is_active", True)
        .execute()
    )
    return r.data or []


def fetch_user_accesses_with_companies(user_id: str) -> List[dict]:
    """user_company_accesses + companies(id, company_name, siret, group_id)."""
    r = (
        supabase.table("user_company_accesses")
        .select(
            "company_id, role, is_primary, companies(id, company_name, siret, group_id)"
        )
        .eq("user_id", user_id)
        .execute()
    )
    return r.data or []


def fetch_target_user_company_ids(user_id: str) -> List[str]:
    """Liste des company_id pour un user (vérification admin commun)."""
    r = (
        supabase.table("user_company_accesses")
        .select("company_id")
        .eq("user_id", user_id)
        .execute()
    )
    return [row["company_id"] for row in (r.data or [])]


def fetch_company_users_rows(company_id: str, role: Optional[str] = None) -> List[dict]:
    """Lignes user_company_accesses + profiles + role_templates pour une company."""
    query = (
        supabase.table("user_company_accesses")
        .select(
            "user_id, role, role_template_id, role_templates(id, name, job_title), profiles!inner(id, first_name, last_name, job_title, created_at)"
        )
        .eq("company_id", company_id)
    )
    if role:
        query = query.eq("role", role)
    r = query.execute()
    return r.data or []


def fetch_active_companies_for_creation() -> List[dict]:
    """Companies actives (champs id, company_name) pour accessible-companies super_admin."""
    r = supabase.table("companies").select("*").eq("is_active", True).execute()
    return r.data or []


def fetch_company_name(company_id: str) -> Optional[str]:
    """Nom d'une company."""
    r = (
        supabase.table("companies")
        .select("company_name")
        .eq("id", company_id)
        .execute()
    )
    return r.data[0]["company_name"] if r.data else None
