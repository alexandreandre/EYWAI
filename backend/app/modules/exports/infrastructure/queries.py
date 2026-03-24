# Requêtes de lecture (exports_history, profiles) — DB Supabase.
# Comportement identique aux accès lecture de api/routers/exports.py.
from typing import Any, Dict, List, Optional

from app.core.database import supabase

LIMIT_HISTORY = 100


def list_exports_by_company(
    company_id: str,
    export_type: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = LIMIT_HISTORY,
) -> List[Dict[str, Any]]:
    """Liste les exports d'une entreprise, triés par date décroissante."""
    query = (
        supabase.table("exports_history")
        .select(
            "id, export_type, period, status, generated_at, generated_by, report, file_paths"
        )
        .eq("company_id", company_id)
        .order("generated_at", desc=True)
        .limit(limit)
    )
    if export_type:
        query = query.eq("export_type", export_type)
    if period:
        query = query.eq("period", period)
    response = query.execute()
    return response.data or []


def get_export_by_id(export_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un export par id et company_id."""
    response = (
        supabase.table("exports_history")
        .select("*")
        .eq("id", export_id)
        .eq("company_id", company_id)
        .single()
        .execute()
    )
    return response.data if response.data else None


def get_user_display_name(user_id: str) -> str:
    """Récupère le prénom et nom d'un utilisateur depuis profiles. Retourne 'Utilisateur' si absent."""
    response = (
        supabase.table("profiles")
        .select("first_name, last_name")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not response.data:
        return "Utilisateur"
    data = response.data
    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    return name or "Utilisateur"


def get_profiles_map(user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Récupère les profils pour une liste d'user_ids. Retourne {user_id: {first_name, last_name}}."""
    if not user_ids:
        return {}
    response = (
        supabase.table("profiles")
        .select("id, first_name, last_name")
        .in_("id", user_ids)
        .execute()
    )
    return {p["id"]: p for p in (response.data or [])}
