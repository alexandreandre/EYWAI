# app/modules/medical_follow_up/infrastructure/company_contact.py
"""Lecture des coordonnées SPST depuis la table companies."""

from typing import Any, Dict, Optional

from app.modules.medical_follow_up.infrastructure.database import get_supabase

_SST_COLUMNS = (
    "service_sante_travail_nom,"
    "service_sante_travail_adresse_rue,"
    "service_sante_travail_adresse_code_postal,"
    "service_sante_travail_adresse_ville,"
    "service_sante_travail_telephone,"
    "service_sante_travail_email"
)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_occupational_health_contact(company_id: str) -> Optional[Dict[str, Optional[str]]]:
    """Retourne les coordonnées SPST ou None si aucun champ renseigné."""
    supabase = get_supabase()
    r = (
        supabase.table("companies")
        .select(_SST_COLUMNS)
        .eq("id", company_id)
        .maybe_single()
        .execute()
    )
    if not r.data:
        return None

    contact = {
        "nom": _clean(r.data.get("service_sante_travail_nom")),
        "adresse_rue": _clean(r.data.get("service_sante_travail_adresse_rue")),
        "adresse_code_postal": _clean(r.data.get("service_sante_travail_adresse_code_postal")),
        "adresse_ville": _clean(r.data.get("service_sante_travail_adresse_ville")),
        "telephone": _clean(r.data.get("service_sante_travail_telephone")),
        "email": _clean(r.data.get("service_sante_travail_email")),
    }
    if not any(contact.values()):
        return None
    return contact
