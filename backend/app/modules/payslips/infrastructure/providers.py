"""
Providers payslips : délégation vers app.shared.infrastructure.payslip_services.

Aucun import legacy (services/*) : tout passe par le pont partagé app/shared/infrastructure.
"""

from __future__ import annotations

from typing import Any

from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.readers import employee_statut_reader
from app.shared.infrastructure.payslip_services import (
    process_payslip_generation,
    process_payslip_generation_forfait,
)


class PayslipGeneratorProvider:
    """Implémentation de IPayslipGenerator (délègue à app.shared.infrastructure.payslip_services)."""

    def generate(self, employee_id: str, year: int, month: int) -> dict[str, Any]:
        """Délègue à generate_forfait ou generate_heures selon le statut."""
        statut = employee_statut_reader.get_employee_statut(employee_id)
        if is_forfait_jour(statut):
            return self.generate_forfait(employee_id, year, month)
        return self.generate_heures(employee_id, year, month)

    def generate_heures(
        self, employee_id: str, year: int, month: int
    ) -> dict[str, Any]:
        return process_payslip_generation(
            employee_id=employee_id,
            year=year,
            month=month,
        )

    def generate_forfait(
        self, employee_id: str, year: int, month: int
    ) -> dict[str, Any]:
        return process_payslip_generation_forfait(
            employee_id=employee_id,
            year=year,
            month=month,
        )

    def generate_en_bac_a_sable(
        self,
        employee_id: str,
        year: int,
        month: int,
        cumuls_precedents: dict | None = None,
    ) -> dict[str, Any]:
        """Calcule le bulletin sans rien écrire (audit, rejeu, contrôle).

        Les cumuls précédents viennent de l'appelant ; le résultat porte
        `payslip_data` et `cumuls` au lieu d'un identifiant et d'une URL.
        """
        bac = BacASable(cumuls_precedents=cumuls_precedents)
        statut = employee_statut_reader.get_employee_statut(employee_id)
        if is_forfait_jour(statut):
            return process_payslip_generation_forfait(
                employee_id=employee_id, year=year, month=month, bac_a_sable=bac
            )
        return process_payslip_generation(
            employee_id=employee_id, year=year, month=month, bac_a_sable=bac
        )


payslip_generator_provider = PayslipGeneratorProvider()
