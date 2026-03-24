# app/modules/cse/infrastructure/queries.py
"""
Requêtes Supabase CSE — accès DB direct (tables cse_*).
Comportement identique aux appels actuels dans le router / application.
"""
from typing import Any, Dict, List, Optional


def fetch_delegation_quotas_for_company(company_id: str) -> List[Dict[str, Any]]:
    """Liste brute des quotas de délégation (avec jointure convention collective)."""
    from app.core.database import supabase

    response = supabase.table("cse_delegation_quotas").select(
        """
        *,
        collective_agreements_catalog!inner(
            id,
            name
        )
        """
    ).eq("company_id", company_id).execute()
    return response.data or []


def fetch_meeting_minutes_path(meeting_id: str) -> Optional[str]:
    """Chemin du PV (minutes_pdf_path) pour une réunion. None si absent."""
    from app.core.database import supabase

    response = (
        supabase.table("cse_meeting_recordings")
        .select("minutes_pdf_path")
        .eq("meeting_id", meeting_id)
        .execute()
    )
    if not response.data or len(response.data) == 0:
        return None
    return response.data[0].get("minutes_pdf_path")
