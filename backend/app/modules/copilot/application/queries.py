"""
Queries (cas d'usage en lecture) du module copilot.

Résolution de contexte (company_id, etc.) utilisée par les commandes.
"""

from __future__ import annotations

from app.modules.copilot.application.service import get_company_id_for_user


def get_company_id_for_user_query(user_id: str) -> str | None:
    """
    Retourne le company_id du profil utilisateur (pour le contexte agent).
    Utilisé par handle_agent_query.
    """
    return get_company_id_for_user(user_id)
