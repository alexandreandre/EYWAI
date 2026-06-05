"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

from typing import Any

from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.onboarding.domain.profile import payroll_block_reason
from app.modules.payslips.application.dto import (
    EditPayslipInput,
    GeneratePayslipInput,
    GeneratePayslipResult,
    PayslipBadRequestError,
    PayslipNotFoundError,
    RestorePayslipInput,
)
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.providers import (
    payslip_editor_provider,
    payslip_generator_provider,
)
from app.modules.payslips.infrastructure.readers import employee_statut_reader

_employee_repository = EmployeeRepository()


def generate_payslip(cmd: GeneratePayslipInput) -> GeneratePayslipResult:
    """
    Génère un bulletin pour un employé / période.
    Logique applicative : récupère le statut employé (via port), choisit forfait jour ou heures,
    délègue au provider (services legacy).
    """
    employee = _employee_repository.get_by_id_only(cmd.employee_id)
    if not employee:
        raise PayslipNotFoundError("Employé non trouvé.")
    block_reason = payroll_block_reason(employee)
    if block_reason:
        raise PayslipBadRequestError(block_reason)

    statut = employee_statut_reader.get_employee_statut(cmd.employee_id)
    if is_forfait_jour(statut):
        result = payslip_generator_provider.generate_forfait(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )
    else:
        result = payslip_generator_provider.generate_heures(
            employee_id=cmd.employee_id,
            year=cmd.year,
            month=cmd.month,
        )
    return GeneratePayslipResult(
        status=result["status"],
        message=result["message"],
        download_url=result["download_url"],
        payslip_id=result.get("payslip_id"),
        warnings=result.get("warnings"),
    )


def delete_payslip(payslip_id: str) -> None:
    """
    Supprime un bulletin (BDD + storage) et déclenche recalc COR.
    Délègue au repository (wrapper legacy ou implémentation future).
    """
    from app.modules.payslips.infrastructure.repository import payslip_repository

    payslip_repository.delete(payslip_id)


def edit_payslip(cmd: EditPayslipInput) -> dict[str, Any]:
    """Sauvegarde les modifications d'un bulletin. Délègue au provider legacy."""
    return payslip_editor_provider.save_edited(
        payslip_id=cmd.payslip_id,
        new_payslip_data=cmd.payslip_data,
        changes_summary=cmd.changes_summary,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
        pdf_notes=cmd.pdf_notes,
        internal_note=cmd.internal_note,
    )


def restore_payslip_version(cmd: RestorePayslipInput) -> dict[str, Any]:
    """Restaure une version d'un bulletin. Délègue au provider legacy."""
    return payslip_editor_provider.restore_version(
        payslip_id=cmd.payslip_id,
        version=cmd.version,
        current_user_id=cmd.current_user_id,
        current_user_name=cmd.current_user_name,
    )
