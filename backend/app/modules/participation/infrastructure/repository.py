"""
Repository participation_simulations (implémentation du port).

Table Supabase : participation_simulations.
Comportement identique au routeur legacy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.participation.domain.entities import ParticipationSimulation
from app.modules.participation.infrastructure.mappers import (
    row_to_participation_simulation,
)


class ParticipationSimulationRepository:
    """
    Implémentation de IParticipationSimulationRepository.
    Accès Supabase via app.core.database.
    """

    def create(self, data: Dict[str, Any], created_by: str) -> ParticipationSimulation:
        """Crée une simulation ; data contient tous les champs sauf created_by (passé à part)."""
        payload = {**data, "created_by": created_by}
        result = supabase.table("participation_simulations").insert(payload).execute()
        if not result.data:
            raise RuntimeError("Insert returned no data")
        return row_to_participation_simulation(result.data[0])

    def get_by_id(
        self, simulation_id: str, company_id: str
    ) -> Optional[ParticipationSimulation]:
        """Retourne une simulation par id si elle appartient à l'entreprise."""
        result = (
            supabase.table("participation_simulations")
            .select("*")
            .eq("id", simulation_id)
            .eq("company_id", company_id)
            .single()
            .execute()
        )
        row = result.data
        # En pratique, single() peut remonter None (not found) ou une valeur
        # non exploitable dans certains mocks/tests : on ne mappe que des dicts.
        if not row or not isinstance(row, dict):
            return None
        return row_to_participation_simulation(row)

    def list_by_company(
        self,
        company_id: str,
        year: Optional[int] = None,
    ) -> List[ParticipationSimulation]:
        """Liste les simulations de l'entreprise, optionnellement filtrées par année."""
        query = (
            supabase.table("participation_simulations")
            .select("*")
            .eq("company_id", company_id)
            .order("year", desc=True)
            .order("created_at", desc=True)
        )
        if year is not None:
            query = query.eq("year", year)
        result = query.execute()
        rows = result.data or []
        return [row_to_participation_simulation(row) for row in rows]

    def delete(self, simulation_id: str, company_id: str) -> bool:
        """Supprime une simulation si elle appartient à l'entreprise."""
        check = (
            supabase.table("participation_simulations")
            .select("id")
            .eq("id", simulation_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not check.data:
            return False
        supabase.table("participation_simulations").delete().eq(
            "id", simulation_id
        ).execute()
        return True

    def exists_with_name(
        self, company_id: str, year: int, simulation_name: str
    ) -> bool:
        """Vérifie si une simulation avec ce nom existe déjà pour l'année."""
        result = (
            supabase.table("participation_simulations")
            .select("id")
            .eq("company_id", company_id)
            .eq("year", year)
            .eq("simulation_name", simulation_name)
            .execute()
        )
        return bool(result.data)
