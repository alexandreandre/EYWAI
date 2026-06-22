"""Résolution convention collective assignée à une entreprise."""

from __future__ import annotations

from typing import Optional, Tuple

from app.core.database import supabase


def resolve_company_collective_agreement(
    company_id: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Retourne (idcc, agreement_id, agreement_name) pour la première CC assignée.
    """
    r = (
        supabase.table("company_collective_agreements")
        .select("collective_agreement_id, collective_agreements_catalog(idcc, name)")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = list(r.data or []) if r else []
    if not rows:
        return None, None, None
    row = rows[0]
    catalog = row.get("collective_agreements_catalog") or {}
    idcc = str(catalog.get("idcc") or "").strip() or None
    agreement_id = str(row.get("collective_agreement_id") or "").strip() or None
    name = str(catalog.get("name") or "").strip() or None
    return idcc, agreement_id, name


def company_has_idcc(company_id: str, idcc: str) -> bool:
    resolved_idcc, _, _ = resolve_company_collective_agreement(company_id)
    return resolved_idcc is not None and resolved_idcc == idcc
