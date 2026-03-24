"""
Providers payslips : délégation vers app.shared.infrastructure.payslip_services.

Aucun import legacy (services/*) : tout passe par le pont partagé app/shared/infrastructure.
"""
from __future__ import annotations

from typing import Any

from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.readers import employee_statut_reader
from app.shared.infrastructure.payslip_services import (
    process_payslip_generation,
    process_payslip_generation_forfait,
    restore_payslip_version as _restore_payslip_version,
    save_edited_payslip as _save_edited_payslip,
)


class PayslipGeneratorProvider:
    """Implémentation de IPayslipGenerator (délègue à app.shared.infrastructure.payslip_services)."""

    def generate(self, employee_id: str, year: int, month: int) -> dict[str, Any]:
        """Délègue à generate_forfait ou generate_heures selon le statut."""
        statut = employee_statut_reader.get_employee_statut(employee_id)
        if is_forfait_jour(statut):
            return self.generate_forfait(employee_id, year, month)
        return self.generate_heures(employee_id, year, month)

    def generate_heures(self, employee_id: str, year: int, month: int) -> dict[str, Any]:
        return process_payslip_generation(
            employee_id=employee_id,
            year=year,
            month=month,
        )

    def generate_forfait(self, employee_id: str, year: int, month: int) -> dict[str, Any]:
        return process_payslip_generation_forfait(
            employee_id=employee_id,
            year=year,
            month=month,
        )


class PayslipEditorProvider:
    """Implémentation de IPayslipEditor (délègue à app.shared.infrastructure.payslip_services)."""

    def save_edited(
        self,
        payslip_id: str,
        new_payslip_data: dict[str, Any],
        changes_summary: str,
        current_user_id: str,
        current_user_name: str,
        pdf_notes: str | None = None,
        internal_note: str | None = None,
    ) -> dict[str, Any]:
        return _save_edited_payslip(
            payslip_id=payslip_id,
            new_payslip_data=new_payslip_data,
            changes_summary=changes_summary,
            current_user_id=current_user_id,
            current_user_name=current_user_name,
            pdf_notes=pdf_notes,
            internal_note=internal_note,
        )

    def restore_version(
        self,
        payslip_id: str,
        version: int,
        current_user_id: str,
        current_user_name: str,
    ) -> dict[str, Any]:
        return _restore_payslip_version(
            payslip_id=payslip_id,
            version=version,
            current_user_id=current_user_id,
            current_user_name=current_user_name,
        )


payslip_generator_provider = PayslipGeneratorProvider()
payslip_editor_provider = PayslipEditorProvider()
