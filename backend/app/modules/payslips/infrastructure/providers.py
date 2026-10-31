"""
Providers payslips : délégation vers app.shared.infrastructure.payslip_services.

Aucun import legacy (services/*) : tout passe par le pont partagé app/shared/infrastructure.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from app.core.lecture_seule import ecritures_permises, lecture_seule
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
        self,
        employee_id: str,
        year: int,
        month: int,
        depart_a_zero: dict | None = None,
        contract_period_id: str | None = None,
    ) -> dict[str, Any]:
        """`depart_a_zero` : choix « en partant de cumuls à zéro » (qui, quand).
        `contract_period_id` : le bulletin du contrat rangé d'un mois partagé [D3]."""
        return process_payslip_generation(
            employee_id=employee_id,
            year=year,
            month=month,
            depart_a_zero=depart_a_zero,
            contract_period_id=contract_period_id,
        )

    def generate_forfait(
        self,
        employee_id: str,
        year: int,
        month: int,
        depart_a_zero: dict | None = None,
        contract_period_id: str | None = None,
    ) -> dict[str, Any]:
        return process_payslip_generation_forfait(
            employee_id=employee_id,
            year=year,
            month=month,
            depart_a_zero=depart_a_zero,
            contract_period_id=contract_period_id,
        )

    def generate_en_bac_a_sable(
        self,
        employee_id: str,
        year: int,
        month: int,
        cumuls_precedents: dict | None = None,
        saisies_en_plus: tuple = (),
    ) -> dict[str, Any]:
        """Calcule le bulletin sans rien écrire (audit, rejeu, contrôle).

        Les cumuls précédents viennent de l'appelant ; le résultat porte
        `payslip_data` et `cumuls` au lieu d'un identifiant et d'une URL.
        `saisies_en_plus` : des saisies du mois qui n'existent qu'en mémoire.

        Le calcul tourne en lecture seule : une écriture faite au passage (le
        droit aux congés d'ancienneté du pied du bulletin) reste en mémoire, et
        toute autre est refusée avant de partir. Un appelant déjà en lecture
        seule (le brut d'une prime) garde son bloc et ses lectures.
        """
        bac = BacASable(
            cumuls_precedents=cumuls_precedents,
            saisies_en_plus=tuple(saisies_en_plus),
        )
        with lecture_seule() if ecritures_permises() else nullcontext():
            statut = employee_statut_reader.get_employee_statut(employee_id)
            if is_forfait_jour(statut):
                return process_payslip_generation_forfait(
                    employee_id=employee_id, year=year, month=month, bac_a_sable=bac
                )
            return process_payslip_generation(
                employee_id=employee_id, year=year, month=month, bac_a_sable=bac
            )


payslip_generator_provider = PayslipGeneratorProvider()
