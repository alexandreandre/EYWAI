"""
Commandes (use cases en écriture) du module payslips.

Logique applicative : décision forfait jour vs heures, délégation aux providers
(services legacy). Les routers n'appellent que ces commandes.
"""

from __future__ import annotations

import logging
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
from app.modules.notifications.application.employee_document_alerts import (
    NOTIFICATION_TYPE_PAYSLIP,
    notify_employee_new_document,
)
from app.modules.employees.application.service import enrich_employee_with_exit_context
from app.shared.domain.employment_rules import payslip_employment_period_block_reason

_employee_repository = EmployeeRepository()
logger = logging.getLogger(__name__)

_PAYSLIP_MONTH_LABELS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _payslip_notification_label(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"Bulletin de paie — {_PAYSLIP_MONTH_LABELS[month - 1]} {year}"
    return f"Bulletin de paie — {month:02d}/{year}"


def _notify_payslip_available(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
) -> None:
    try:
        notify_employee_new_document(
            employee_id,
            company_id,
            _payslip_notification_label(year, month),
            page_path="payslips",
            notification_type=NOTIFICATION_TYPE_PAYSLIP,
        )
    except Exception as exc:
        logger.info(
            "[doc_notif] Bulletin non notifié pour %s (%02d/%d): %s",
            employee_id,
            month,
            year,
            exc,
        )


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
    employee = enrich_employee_with_exit_context(employee)
    period_block_reason = payslip_employment_period_block_reason(
        employee, cmd.year, cmd.month
    )
    if period_block_reason:
        raise PayslipBadRequestError(period_block_reason)

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

    if str(result.get("status") or "") == "success":
        company_id = str(employee.get("company_id") or "").strip()
        if company_id:
            _notify_payslip_available(cmd.employee_id, company_id, cmd.year, cmd.month)

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
