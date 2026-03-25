"""
Centralisation de la création et de l'accès aux clients Supabase.

Stratégie unifiée :
- get_supabase_client() : client par défaut (SUPABASE_KEY, usage API courant).
- get_supabase_admin_client() : client avec privilèges admin (SUPABASE_SERVICE_KEY
  ou SUPABASE_SERVICE_ROLE_KEY, sinon repli sur SUPABASE_KEY).
- Les variables de module `supabase`, `supabase_url`, `supabase_key` permettent
  une migration progressive : le code legacy peut continuer à importer depuis
  core.config (wrapper) sans changement.

Inventaire des usages actuels de create_client (à migrer progressivement) :
- app/core/config.py : utilise ce module (déjà centralisé).
- backend_api/core/config.py : wrapper qui réexporte depuis app.core.config.
- api/routers/copilot.py, copilot_agent.py, rates.py : client local → migrer vers get_supabase_client() ou get_supabase_admin_client() selon besoin.
- api/routers/auth.py : auth_client / admin_client inline → migrer vers get_supabase_admin_client().
- api/routers/super_admin.py : admin_client inline → get_supabase_admin_client().
- api/routers/user_creation.py : admin_supabase inline (SERVICE_ROLE_KEY) → get_supabase_admin_client().
- scraping/*/orchestrator.py : client local avec SUPABASE_SERVICE_KEY → get_supabase_admin_client().
- Moteur paie (contexte, calcul_net, calcul_cotisations, etc.) : variables d’environnement Supabase ; à terme injecter un client ou utiliser get_supabase_admin_client().
- tests : garder imports depuis core.config ou utiliser get_supabase_client().

Ne pas remplacer tous les appels d'un coup : migrer module par module en important
depuis app.core.database et en utilisant get_supabase_client() ou get_supabase_admin_client().
"""
from __future__ import annotations

from supabase import Client, create_client

from app.core.settings import (
    get_supabase_admin_env,
    require_supabase_env,
)

# --- Client par défaut (clé anon/standard) ---
_default_url, _default_key = require_supabase_env()
supabase: Client = create_client(_default_url, _default_key)
supabase_url: str = _default_url
supabase_key: str = _default_key


def get_supabase_client() -> Client:
    """Retourne le client Supabase par défaut (SUPABASE_URL + SUPABASE_KEY)."""
    return supabase


def get_supabase_admin_client() -> Client:
    """
    Retourne un client Supabase avec privilèges admin (service_role).
    Utilise SUPABASE_SERVICE_KEY ou SUPABASE_SERVICE_ROLE_KEY si présents,
    sinon repli sur SUPABASE_KEY pour compatibilité.
    """
    url, key = get_supabase_admin_env()
    return create_client(url, key)
