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
    """Liste des employés de l'entreprise (id, company_id)."""
    resp = (
        supabase.table("employees")
        .select("id, company_id")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []
