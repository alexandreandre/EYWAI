"""
Requêtes Supabase réutilisables pour company_groups.

Fonctions de lecture DB (select) utilisables par le repository ou la couche application.
Comportement identique aux appels dans api/routers/company_groups.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase


def fetch_group_by_id_with_companies(
    group_id: str,
) -> Optional[Dict[str, Any]]:
    """Récupère un groupe par id avec ses entreprises (nested)."""
    res = (
        supabase.table("company_groups")
        .select("*, companies(id, company_name, siret, is_active)")
        .eq("id", group_id)
        .execute()
    )
    if not res.data:
        return None
    return res.data[0]


def fetch_groups_with_companies(
    company_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Récupère les groupes avec leurs entreprises.
    company_ids is None ou vide : tous les groupes actifs.
    Sinon : groupes ayant au moins une company dans company_ids (companies!inner).
    """
    if company_ids is None or len(company_ids) == 0:
        res = (
            supabase.table("company_groups")
            .select("*, companies(id, company_name, siret, is_active)")
            .eq("is_active", True)
            .execute()
        )
    else:
        res = (
            supabase.table("company_groups")
            .select("*, companies!inner(id, company_name, siret, is_active)")
            .in_("companies.id", company_ids)
            .eq("is_active", True)
            .execute()
        )
    return res.data or []


def fetch_all_active_groups_ordered() -> List[Dict[str, Any]]:
    """Liste tous les groupes actifs triés par group_name."""
    res = (
        supabase.table("company_groups")
        .select("*")
        .eq("is_active", True)
        .order("group_name")
        .execute()
    )
    return res.data or []


def fetch_company_ids_by_group_id(group_id: str) -> List[str]:
    """IDs des entreprises actives d'un groupe."""
    res = (
        supabase.table("companies")
        .select("id")
        .eq("group_id", group_id)
        .eq("is_active", True)
        .execute()
    )
    return [c["id"] for c in (res.data or [])]


def fetch_companies_by_group_id(
    group_id: str,
    columns: str = "id, company_name, siret, effectif, is_active",
) -> List[Dict[str, Any]]:
    """Liste des entreprises d'un groupe (colonnes configurables)."""
    res = (
        supabase.table("companies")
        .select(columns)
        .eq("group_id", group_id)
        .eq("is_active", True)
        .order("company_name")
        .execute()
    )
    return res.data or []


def fetch_companies_without_group(
    columns: str = "id, company_name, siret, effectif",
) -> List[Dict[str, Any]]:
    """Entreprises sans groupe (group_id null)."""
    res = (
        supabase.table("companies")
        .select(columns)
        .is_("group_id", "null")
        .eq("is_active", True)
        .order("company_name")
        .execute()
    )
    return res.data or []


def fetch_companies_for_group_stats(
    group_id: str,
    columns: str = "id, company_name, siret",
) -> List[Dict[str, Any]]:
    """Entreprises du groupe pour stats (consolidated, etc.)."""
    res = (
        supabase.table("companies")
        .select(columns)
        .eq("group_id", group_id)
        .eq("is_active", True)
        .execute()
    )
    return res.data or []


def fetch_group_company_ids_for_permission_check(group_id: str) -> List[str]:
    """IDs des entreprises du groupe (toutes, pour vérification admin)."""
    res = supabase.table("companies").select("id").eq("group_id", group_id).execute()
    return [c["id"] for c in (res.data or [])]


def fetch_company_effectif_by_group_id(group_id: str) -> List[Dict[str, Any]]:
    """Pour un groupe, retourne les lignes (id, effectif) des companies actives."""
    res = (
        supabase.table("companies")
        .select("id, effectif")
        .eq("group_id", group_id)
        .eq("is_active", True)
        .execute()
    )
    return res.data or []
