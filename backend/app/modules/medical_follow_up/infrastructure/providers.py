# app/modules/medical_follow_up/infrastructure/providers.py
"""
Providers du module suivi médical : settings « module activé ».

Implémentation de ICompanyMedicalSettingsProvider.
Lit companies.settings.medical_follow_up_enabled (défaut True, comportement identique au legacy).
Aucune dépendance à services/*.
"""

from app.modules.medical_follow_up.domain.interfaces import ICompanyMedicalSettingsProvider
from app.modules.medical_follow_up.infrastructure.database import get_supabase


class CompanyMedicalSettingsProvider(ICompanyMedicalSettingsProvider):
    """Indique si le module suivi médical est activé pour une entreprise."""

    def is_enabled(self, company_id: str) -> bool:
        supabase = get_supabase()
        r = (
            supabase.table("companies")
            .select("settings")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
        if not r.data:
            return True  # défaut identique au legacy
        settings = r.data.get("settings") or {}
        return bool(settings.get("medical_follow_up_enabled", True))
