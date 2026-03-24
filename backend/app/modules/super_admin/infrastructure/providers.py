"""
Providers infrastructure du module super_admin.

Auth admin Supabase : create_user, get_user_by_id, update_user, delete_user.
Utilise app.core.database.get_supabase_admin_client().
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.database import get_supabase_admin_client


def _admin_client():
    return get_supabase_admin_client()


def get_user_email(user_id: str) -> Optional[str]:
    """Récupère l'email d'un utilisateur depuis Auth (admin)."""
    try:
        auth_response = _admin_client().auth.admin.get_user_by_id(user_id)
        return auth_response.user.email if auth_response and auth_response.user else None
    except Exception:
        return None


def create_user(email: str, password: str, user_metadata: Dict[str, Any]) -> Any:
    """Crée un utilisateur dans Auth (admin). Retourne l'objet auth response (auth_response.user.id)."""
    return _admin_client().auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": user_metadata or {},
    })


def delete_user(user_id: str) -> None:
    """Supprime un utilisateur Auth."""
    _admin_client().auth.admin.delete_user(user_id)


def update_user(user_id: str, attributes: Dict[str, Any]) -> None:
    """Met à jour un utilisateur Auth (ex. email)."""
    _admin_client().auth.admin.update_user_by_id(user_id, attributes)
