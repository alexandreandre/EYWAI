"""
Commandes applicatives : génération et édition des bulletins de paie.
Les routers appellent exclusivement ce module (jamais documents/ ou engine directement).
"""

from __future__ import annotations

from typing import Any


def is_forfait_jour(statut: str | None) -> bool:
    """Détecte si un employé est en forfait jour selon son statut."""
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def process_payslip_generation(employee_id: str, year: int, month: int) -> dict[str, Any]:
    """Génère une fiche de paie (heures). Délègue à documents.payslip_generator."""
    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation as _impl,
    )
    return _impl(employee_id=employee_id, year=year, month=month)


def process_payslip_generation_forfait(
    employee_id: str, year: int, month: int
) -> dict[str, Any]:
    """Génère une fiche de paie forfait jour. Délègue à documents.payslip_generator_forfait."""
    from app.modules.payroll.documents.payslip_generator_forfait import (
        process_payslip_generation_forfait as _impl,
    )
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
    """Enregistre un bulletin édité. Délègue à documents.payslip_editor."""
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
    """Restaure une version précédente d'un bulletin. Délègue à documents.payslip_editor."""
    from app.modules.payroll.documents.payslip_editor import (
        restore_payslip_version as _impl,
    )
    return _impl(
        payslip_id=payslip_id,
        version=version,
        current_user_id=current_user_id,
        current_user_name=current_user_name,
    )
