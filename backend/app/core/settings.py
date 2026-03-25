"""
Centralisation des variables d'environnement.
Utilisé par app.core.config ; le legacy continue d'utiliser backend_api/core/config.py.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Clé service_role (optionnelle ; pour admin / opérations bypass RLS)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def require_supabase_env() -> tuple[str, str]:
    """Retourne (SUPABASE_URL, SUPABASE_KEY) ou lève RuntimeError si manquants."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Variables d'environnement SUPABASE manquantes.")
    return SUPABASE_URL, SUPABASE_KEY


def get_supabase_admin_env() -> tuple[str, str]:
    """
    Retourne (url, key) pour un client Supabase admin (service_role).
    Ordre de priorité : SUPABASE_SERVICE_KEY, puis SUPABASE_SERVICE_ROLE_KEY, puis SUPABASE_KEY.
    """
    url = SUPABASE_URL
    key = SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    if not url or not key:
        raise RuntimeError(
            "Variables d'environnement SUPABASE manquantes pour le client admin "
            "(SUPABASE_URL et SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY)."
        )
    return url, key
