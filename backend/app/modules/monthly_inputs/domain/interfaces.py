"""
Ports (interfaces) du domaine monthly_inputs.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni DB ici.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IMonthlyInputsRepository(ABC):
    """Accès à la table monthly_inputs (CRUD)."""

    @abstractmethod
    def list_by_period(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Liste toutes les saisies du mois (tous salariés). Ordre created_at desc."""
        ...

    @abstractmethod
    def list_by_employee_period(
        self, employee_id: str, year: int, month: int
    ) -> List[Dict[str, Any]]:
        """Liste les saisies d'un employé pour un mois donné."""
        ...

    @abstractmethod
    def insert_batch(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insère plusieurs saisies. Retourne les lignes insérées."""
        ...

    @abstractmethod
    def insert_one(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Insère une saisie. Retourne la ligne insérée."""
        ...

    @abstractmethod
    def delete_by_id(self, input_id: str) -> None:
        """Supprime une saisie par id."""
        ...

    @abstractmethod
    def delete_by_id_and_employee(self, input_id: str, employee_id: str) -> None:
        """Supprime une saisie par id et employee_id."""
        ...


class IPrimesCatalogueProvider(ABC):
    """Port pour le catalogue de primes (payroll_config). Implémentation en infrastructure."""

    @abstractmethod
    def get_primes_catalogue(self) -> List[Any]:
        """Retourne la liste des primes du catalogue (structure dict/list)."""
        ...
