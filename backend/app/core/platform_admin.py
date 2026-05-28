"""
Helpers pour les administrateurs plateforme EYWAI (ex-super admins).

Un admin plateforme a accès à l'interface Administration et à l'interface RH
avec tous les droits sur toutes les entreprises.
"""

from __future__ import annotations

from typing import Any


def is_platform_admin(user: Any) -> bool:
    """True si l'utilisateur est admin plateforme (table super_admins active)."""
    return bool(
        getattr(user, "is_platform_admin", False)
        or getattr(user, "is_super_admin", False)
    )
