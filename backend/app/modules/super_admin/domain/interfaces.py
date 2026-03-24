"""
Interfaces du domaine super_admin.

Contrats pour repository (super_admins) et provider Auth admin.
Implémentés dans infrastructure (repository.py, providers.py).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from app.modules.super_admin.domain.entities import SuperAdmin


class ISuperAdminRepository(Protocol):
    """Accès lecture super_admins (table)."""

    def get_by_user_id(self, user_id: UUID) -> Optional[SuperAdmin]:
        """Retourne le super admin actif pour ce user_id, ou None."""
        ...

    def list_all(self) -> List[SuperAdmin]:
        """Liste tous les super admins (actifs)."""
        ...


class IAuthAdminProvider(Protocol):
    """
    Opérations Auth Supabase (admin) : create_user, get_user_by_id, update_user, delete_user.
    À implémenter via get_supabase_admin_client() (app.core.database).
    """
    # Placeholder : signature minimale pour préparation migration
    def get_user_email(self, user_id: str) -> Optional[str]:
        """Récupère l'email d'un utilisateur depuis Auth."""
        ...

    def create_user(self, email: str, password: str, user_metadata: Dict[str, Any]) -> Any:
        """Crée un utilisateur dans Auth (admin)."""
        ...

    def delete_user(self, user_id: str) -> None:
        """Supprime un utilisateur Auth."""
        ...

    def update_user(self, user_id: str, attributes: Dict[str, Any]) -> None:
        """Met à jour un utilisateur Auth (ex. email)."""
        ...
