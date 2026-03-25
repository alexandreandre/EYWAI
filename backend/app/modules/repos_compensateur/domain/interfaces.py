"""
Ports (interfaces) pour le module repos_compensateur.

L’infrastructure implémente ces interfaces ; l’application ne dépend que des abstractions.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.modules.repos_compensateur.domain.entities import ReposCredit


class IReposCreditsRepository(Protocol):
    """Accès persistance à la table repos_compensateur_credits."""

    def upsert_credit(self, credit: ReposCredit) -> None:
        """Upsert une ligne (employee_id, year, month, source)."""
        ...

    def get_jours_by_employee_year(
        self, employee_ids: list[str], year: int
    ) -> dict[str, float]:
        """Somme des jours par employee_id pour l’année (pour soldes)."""
        ...


class IPayslipDataProvider(Protocol):
    """
    Fournit les données bulletins (payslip_data) pour le calcul des HS / COR.

    Source actuelle : table payslips, colonne payslip_data.calcul_du_brut.
    """

    def get_bulletins_par_mois(
        self, company_id: str, year: int, employee_ids: list[str]
    ) -> dict[str, dict[int, dict[str, Any]]]:
        """
        Retourne pour chaque employee_id un dict { month: payslip_data }.
        """
        ...
