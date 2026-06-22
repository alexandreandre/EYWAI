"""Port persistance cumuls exonération JEI (plafond 5 PASS)."""

from abc import ABC, abstractmethod


class AbstractJeiExonerationsRepository(ABC):
    """Suivi mensuel des exonérations JEI par établissement."""

    @abstractmethod
    def sum_annual_excluding_month(
        self,
        company_id: str,
        year: int,
        exclude_employee_id: str,
        exclude_month: int,
    ) -> float:
        """Somme des montants exonérés sur l'année, hors le couple employé/mois en cours."""
        ...

    @abstractmethod
    def upsert_monthly(
        self,
        company_id: str,
        year: int,
        month: int,
        employee_id: str,
        montant_exonere: float,
    ) -> None:
        """Enregistre ou met à jour le montant exonéré du mois (idempotent)."""
        ...
