# Requêtes métier auth : profil (nom d’affichage pour email reset).
# Comportement identique au code legacy (table profiles).

from __future__ import annotations

from app.core.database import supabase


def get_profile_display_name(user_id: str, fallback_email_local: str) -> str:
    """
    Retourne le nom d’affichage du profil (first_name + last_name).
    Si pas de profil ou nom vide, retourne fallback_email_local (ex. partie avant @ de l’email).
    """
    resp = (
        supabase.table("profiles")
        .select("id, first_name, last_name, role")
        .eq("id", user_id)
        .execute()
    )
    if not resp.data or len(resp.data) == 0:
        return fallback_email_local
    profile = resp.data[0]
    name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
    return name if name else fallback_email_local


def get_employees_debug_snapshot() -> list[dict]:
    """Snapshot de la table employees pour logs de debug (login username inconnu)."""
    resp = supabase.table("employees").select("*").execute()
    return resp.data if resp.data else []
