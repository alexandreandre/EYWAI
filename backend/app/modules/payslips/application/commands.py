"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

from typing import Any

from app.modules.payslips.application.dto import (
    EditPayslipInput,
    GeneratePayslipInput,
    GeneratePayslipResult,
    RestorePayslipInput,
)
from app.modules.payslips.domain.rules import is_forfait_jour
from app.modules.payslips.infrastructure.providers import (
    payslip_editor_provider,
    payslip_generator_provider,
)
from app.modules.payslips.infrastructure.readers import employee_statut_reader


def generate_payslip(cmd: GeneratePayslipInput) -> GeneratePayslipResult:
    """
    Génère un bulletin pour un employé / période.
    Logique applicative : récupère le statut employé (via port), choisit forfait jour ou heures,
    délègue au provider (services legacy).
    """
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
