"""
Centralisation des variables d'environnement.
Utilisé par app.core.config ; le legacy continue d'utiliser backend_api/core/config.py.
"""

import base64
import json
import os

from dotenv import load_dotenv

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Clé service_role (optionnelle ; pour admin / opérations bypass RLS)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# OpenRouter (clé API ; les modèles sont définis dans app.shared.infrastructure.ai.models)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def require_supabase_env() -> tuple[str, str]:
    """Retourne (SUPABASE_URL, SUPABASE_KEY) ou lève RuntimeError si manquants."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Variables d'environnement SUPABASE manquantes.")
    return SUPABASE_URL, SUPABASE_KEY


def _jwt_role(supabase_jwt: str) -> str | None:
    """Lit le champ 'role' du JWT Supabase (sans vérification cryptographique)."""
    try:
        parts = supabase_jwt.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        pad = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        r = payload.get("role")
        return str(r) if r is not None else None
    except Exception:
        return None


def get_supabase_admin_env() -> tuple[str, str]:
    """
    Retourne (url, key) pour un client Supabase admin (service_role).

    Choix de la clé : préfère une JWT dont le rôle est ``service_role`` parmi
    SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY (certains .env
    utilisent SUPABASE_KEY pour la service_role et une autre variable pour anon).
    """
    url = SUPABASE_URL
    if not url:
        raise RuntimeError("Variable d'environnement SUPABASE_URL manquante.")

    candidates = [
        k for k in (SUPABASE_SERVICE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY) if k
    ]
    for key in candidates:
        if _jwt_role(key) == "service_role":
            return url, key

    key = SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    if not key:
        raise RuntimeError(
            "Variables d'environnement Supabase manquantes pour le client admin "
            "(SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY)."
        )
    return url, key
