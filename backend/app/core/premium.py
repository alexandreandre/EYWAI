"""Lecture du statut premium côté entreprise (table companies)."""

from app.core.database import supabase


def is_company_premium(company_id: str) -> bool:
    if not company_id:
        return False
    r = (
        supabase.table("companies")
        .select("is_premium")
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    data = r.data if r else None
    if not data:
        return False
    return bool(data.get("is_premium"))
