"""
Repository companies : implémentation ICompanyRepository.

Utilise app.core.database (client Supabase) — module autonome, sans dépendance legacy.
"""

from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.companies.domain.interfaces import ICompanyRepository


class SupabaseCompanyRepository(ICompanyRepository):
    """Implémentation Supabase pour lecture/écriture companies."""

    def get_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("companies")
            .select("*")
            .eq("id", company_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def get_settings(self, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("companies")
            .select("settings")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if not r.data:
            return None
        return r.data.get("settings") or {}

    def update_settings(self, company_id: str, settings: Dict[str, Any]) -> None:
        supabase.table("companies").update({"settings": settings}).eq(
            "id", company_id
        ).execute()


# Instance partagée (injection future possible)
company_repository = SupabaseCompanyRepository()
