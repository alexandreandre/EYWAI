"""
Ports (interfaces) pour le module bonus_types.

L’infrastructure implémente ces interfaces ; l’application ne dépend que des abstractions.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.bonus_types.domain.entities import BonusType


class IBonusTypeRepository(Protocol):
    """Accès persistance aux primes catalogue (table company_bonus_types)."""

    def list_by_company(self, company_id: str) -> list[BonusType]:
        """Liste les primes du catalogue pour une entreprise (ordre libelle)."""
        ...

    def get_by_id(
        self, bonus_type_id: str, company_id: str | None = None
    ) -> BonusType | None:
        """Retourne une prime par id ; si company_id fourni, vérifie l’appartenance."""
        ...

    def create(self, entity: BonusType) -> BonusType:
        """Crée une prime ; l’entity doit avoir company_id et created_by."""
        ...

    def update(self, bonus_type_id: str, data: dict[str, Any]) -> BonusType | None:
        """Met à jour une prime ; retourne l’entité mise à jour ou None si non trouvée."""
        ...

    def delete(self, bonus_type_id: str) -> bool:
        """Supprime une prime ; retourne True si supprimée."""
        ...


class IEmployeeHoursProvider(Protocol):
    """
    Fournit les heures réalisées d’un employé sur un mois (pour calcul prime selon_heures).

    Source actuelle : table employee_schedules, champ actual_hours.calendrier_reel.
    """

    def get_total_actual_hours(
        self,
        employee_id: str,
        year: int,
        month: int,
    ) -> float:
        """Somme des heures_faites sur le mois (calendrier_reel)."""
        ...
