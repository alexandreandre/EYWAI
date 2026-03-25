"""
Ports (interfaces) pour le module uploads.

Aucune dépendance à FastAPI ni à la base : l'infrastructure implémente ces interfaces.
À migrer depuis api/routers/uploads.py (storage Supabase logos, tables companies/company_groups).
"""
from __future__ import annotations

from typing import Protocol


class ILogoStorage(Protocol):
    """Stockage des fichiers logo (bucket Supabase 'logos')."""

    def upload(
        self,
        path: str,
        content: bytes,
        content_type: str,
    ) -> None:
        """Envoie le fichier au storage. Lève en cas d'erreur."""
        ...

    def get_public_url(self, path: str) -> str:
        """Retourne l'URL publique du fichier."""
        ...

    def remove(self, paths: list[str]) -> None:
        """Supprime un ou plusieurs fichiers. Peut ignorer les erreurs (log)."""
        ...


class ILogoRepository(Protocol):
    """Persistance logo_url / logo_scale (tables companies, company_groups)."""

    def entity_exists(self, entity_type: str, entity_id: str) -> bool:
        """Retourne True si l'entité existe (au moins une ligne)."""
        ...

    def get_logo_url(self, entity_type: str, entity_id: str) -> str | None:
        """Retourne l'URL du logo ou None si absent."""
        ...

    def update_logo_url(self, entity_type: str, entity_id: str, logo_url: str | None) -> bool:
        """Met à jour logo_url. Retourne True si une ligne a été mise à jour."""
        ...

    def update_logo_scale(self, entity_type: str, entity_id: str, scale: float) -> bool:
        """Met à jour logo_scale. Retourne True si une ligne a été mise à jour."""
        ...


class ILogoPermissionChecker(Protocol):
    """Vérification des droits pour modifier le logo d'une entité."""

    def can_edit_entity_logo(
        self,
        user_id: str,
        is_super_admin: bool,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        """
        Retourne True si l'utilisateur peut modifier le logo.
        company : admin ou rh de cette company, ou super_admin.
        group : super_admin uniquement.
        """
        ...
