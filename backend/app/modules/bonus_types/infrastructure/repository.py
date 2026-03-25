"""
Implémentation du port IBonusTypeRepository via Supabase (table company_bonus_types).
"""
from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.infrastructure.mappers import (
    bonus_type_to_row,
    row_to_bonus_type,
)
from app.modules.bonus_types.infrastructure.queries import TABLE_COMPANY_BONUS_TYPES


class SupabaseBonusTypeRepository:
    """Repository bonus_types sur table company_bonus_types."""

    def list_by_company(self, company_id: str) -> list[BonusType]:
        """Liste les primes du catalogue pour une entreprise (ordre libelle)."""
        response = (
            supabase.table(TABLE_COMPANY_BONUS_TYPES)
            .select("*")
            .eq("company_id", company_id)
            .order("libelle")
            .execute()
        )
        return [row_to_bonus_type(row) for row in (response.data or [])]

    def get_by_id(
        self,
        bonus_type_id: str,
        company_id: str | None = None,
    ) -> BonusType | None:
        """Retourne une prime par id ; si company_id fourni, filtre dessus."""
        query = (
            supabase.table(TABLE_COMPANY_BONUS_TYPES)
            .select("*")
            .eq("id", bonus_type_id)
        )
        if company_id is not None:
            query = query.eq("company_id", company_id)
        response = query.maybe_single().execute()
        if not response.data:
            return None
        return row_to_bonus_type(response.data)

    def create(self, entity: BonusType) -> BonusType:
        """Crée une prime ; retourne l'entité avec id/created_at renseignés."""
        row = bonus_type_to_row(entity)
        response = supabase.table(TABLE_COMPANY_BONUS_TYPES).insert(row).execute()
        if not response.data:
            return entity
        return row_to_bonus_type(response.data[0])

    def update(
        self,
        bonus_type_id: str,
        data: dict[str, Any],
    ) -> BonusType | None:
        """Met à jour une prime ; retourne l'entité mise à jour ou None."""
        # Nettoyer les clés None pour un PATCH propre
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return self.get_by_id(bonus_type_id, None)
        response = (
            supabase.table(TABLE_COMPANY_BONUS_TYPES)
            .update(update_data)
            .eq("id", bonus_type_id)
            .execute()
        )
        if not response.data:
            return None
        return row_to_bonus_type(response.data[0])

    def delete(self, bonus_type_id: str) -> bool:
        """Supprime une prime. Retourne True si supprimée."""
        supabase.table(TABLE_COMPANY_BONUS_TYPES).delete().eq(
            "id", bonus_type_id
        ).execute()
        return True
