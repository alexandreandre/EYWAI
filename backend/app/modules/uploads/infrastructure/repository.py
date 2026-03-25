"""
Repository logos : accès aux tables companies et company_groups (logo_url, logo_scale).

Implémente ILogoRepository (domain). Comportement identique à api/routers/uploads.py.
"""
from __future__ import annotations

from app.core.database import supabase

from app.modules.uploads.domain.interfaces import ILogoRepository


def _table_name(entity_type: str) -> str:
    """Table cible selon entity_type (company -> companies, group -> company_groups)."""
    return "companies" if entity_type == "company" else "company_groups"


class LogoRepository:
    """Implémentation Supabase de ILogoRepository."""

    def entity_exists(self, entity_type: str, entity_id: str) -> bool:
        """Retourne True si l'entité existe (au moins une ligne)."""
        table = _table_name(entity_type)
        result = supabase.table(table).select("id").eq("id", entity_id).execute()
        return bool(result.data and len(result.data) > 0)

    def get_logo_url(self, entity_type: str, entity_id: str) -> str | None:
        """Retourne l'URL du logo ou None (None si entité absente ou logo_url null)."""
        table = _table_name(entity_type)
        result = (
            supabase.table(table).select("logo_url").eq("id", entity_id).execute()
        )
        if not result.data or len(result.data) == 0:
            return None
        return result.data[0].get("logo_url")

    def update_logo_url(
        self, entity_type: str, entity_id: str, logo_url: str | None
    ) -> bool:
        """Met à jour logo_url. Retourne True si au moins une ligne mise à jour."""
        table = _table_name(entity_type)
        result = (
            supabase.table(table)
            .update({"logo_url": logo_url})
            .eq("id", entity_id)
            .execute()
        )
        return bool(result.data and len(result.data) > 0)

    def update_logo_scale(
        self, entity_type: str, entity_id: str, scale: float
    ) -> bool:
        """Met à jour logo_scale. Retourne True si au moins une ligne mise à jour."""
        table = _table_name(entity_type)
        result = (
            supabase.table(table)
            .update({"logo_scale": scale})
            .eq("id", entity_id)
            .execute()
        )
        return bool(result.data and len(result.data) > 0)


_default_repository: ILogoRepository = LogoRepository()


def entity_exists(entity_type: str, entity_id: str) -> bool:
    """Retourne True si l'entité existe (au moins une ligne)."""
    return _default_repository.entity_exists(entity_type, entity_id)


def get_logo_url(entity_type: str, entity_id: str) -> str | None:
    """Retourne l'URL du logo ou None (None si entité absente ou logo_url null)."""
    return _default_repository.get_logo_url(entity_type, entity_id)


def update_logo_url(
    entity_type: str, entity_id: str, logo_url: str | None
) -> bool:
    """Met à jour logo_url. Retourne True si au moins une ligne mise à jour."""
    return _default_repository.update_logo_url(
        entity_type, entity_id, logo_url
    )


def update_logo_scale(entity_type: str, entity_id: str, scale: float) -> bool:
    """Met à jour logo_scale. Retourne True si au moins une ligne mise à jour."""
    return _default_repository.update_logo_scale(
        entity_type, entity_id, scale
    )
