"""
Pont unique app/* vers la génération/édition de bulletins (app.modules.payroll.documents) et recalc COR.

Délègue à app.modules.payroll.documents pour payslip_generator, payslip_editor, forfait ;
recalcul COR via app.modules.repos_compensateur.application.service.
Import paresseux pour limiter le chargement.
"""
from __future__ import annotations

from typing import Any


def process_payslip_generation(employee_id: str, year: int, month: int) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_generator (comportement identique)."""
    from app.modules.payroll.documents.payslip_generator import process_payslip_generation as _impl
    return _impl(employee_id=employee_id, year=year, month=month)


def process_payslip_generation_forfait(
    employee_id: str, year: int, month: int
) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_generator_forfait (comportement identique)."""
    from app.modules.payroll.documents.payslip_generator_forfait import process_payslip_generation_forfait as _impl
    return _impl(employee_id=employee_id, year=year, month=month)


def save_edited_payslip(
    payslip_id: str,
    new_payslip_data: dict[str, Any],
    changes_summary: str,
    current_user_id: str,
    current_user_name: str,
    pdf_notes: str | None = None,
    internal_note: str | None = None,
) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_editor (comportement identique)."""
    from app.modules.payroll.documents.payslip_editor import save_edited_payslip as _impl
    return _impl(
        payslip_id=payslip_id,
        new_payslip_data=new_payslip_data,
        changes_summary=changes_summary,
        current_user_id=current_user_id,
        current_user_name=current_user_name,
        pdf_notes=pdf_notes,
        internal_note=internal_note,
    )


def restore_payslip_version(
    payslip_id: str,
    version: int,
    current_user_id: str,
    current_user_name: str,
) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_editor (comportement identique)."""
    from app.modules.payroll.documents.payslip_editor import restore_payslip_version as _impl
    return _impl(
        payslip_id=payslip_id,
        version=version,
        current_user_id=current_user_id,
        current_user_name=current_user_name,
    )


def recalculer_credits_repos_employe(
    employee_id: str, company_id: str, year: int
) -> int:
    """Délègue à app.modules.repos_compensateur.application.service (comportement identique à l’ancien recalc_service)."""
    from app.modules.repos_compensateur.application.service import (
        recalculer_credits_repos_employe as _impl,
    )
    return _impl(employee_id=employee_id, company_id=company_id, year=year)
