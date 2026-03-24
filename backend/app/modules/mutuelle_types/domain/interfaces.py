"""
Ports (interfaces) pour le module mutuelle_types.

L’infrastructure implémente ces interfaces ; l’application ne dépend que des abstractions.
Tables : company_mutuelle_types, employee_mutuelle_types, employees.specificites_paie (mutuelle).
"""
from __future__ import annotations

from typing import Any, Protocol

from app.modules.mutuelle_types.domain.entities import MutuelleType


class IMutuelleTypeRepository(Protocol):
    """Accès persistance aux formules mutuelle (company_mutuelle_types, employee_mutuelle_types)."""

    def list_by_company(self, company_id: str) -> list[MutuelleType]:
        """Liste les formules mutuelle du catalogue pour une entreprise (ordre libelle)."""
        ...

    def get_by_id(
        self,
        mutuelle_type_id: str,
        company_id: str | None = None,
    ) -> MutuelleType | None:
        """Retourne une formule par id ; si company_id fourni, vérifie l’appartenance."""
        ...

    def create(self, entity: MutuelleType, created_by: str) -> MutuelleType:
        """Crée une formule ; l’entity doit avoir company_id ; retourne l’entité avec id/created_at."""
        ...

    def update(
        self,
        mutuelle_type_id: str,
        data: dict[str, Any],
    ) -> MutuelleType | None:
        """Met à jour une formule ; retourne l’entité mise à jour ou None si non trouvée."""
        ...

    def delete(self, mutuelle_type_id: str) -> bool:
        """Supprime une formule ; retourne True si supprimée."""
        ...

    def find_by_company_and_libelle(
        self,
        company_id: str,
        libelle: str,
        exclude_id: str | None = None,
    ) -> MutuelleType | None:
        """Retourne une formule avec ce (company_id, libelle) si elle existe, sinon None. exclude_id pour mise à jour."""
        ...

    def list_employee_ids(self, mutuelle_type_id: str) -> list[str]:
        """Liste les employee_id associés à cette formule (table employee_mutuelle_types)."""
        ...

    def set_employee_associations(
        self,
        mutuelle_type_id: str,
        employee_ids: list[str],
        created_by: str,
        company_id: str,
    ) -> None:
        """
        Remplace les associations employés pour cette formule.
        Crée les lignes employee_mutuelle_types et met à jour employees.specificites_paie.mutuelle.
        """
        ...

    def remove_employee_associations_and_sync_specificites(
        self,
        mutuelle_type_id: str,
        employee_ids: list[str],
    ) -> None:
        """
        Retire les associations pour les employés donnés et met à jour their specificites_paie.mutuelle.
        """
        ...

    def validate_employee_ids_belong_to_company(
        self, company_id: str, employee_ids: list[str]
    ) -> list[str]:
        """Retourne la sous-liste des employee_ids qui appartiennent à l’entreprise ; si len != len(employee_ids) alors certains sont invalides."""
        ...
