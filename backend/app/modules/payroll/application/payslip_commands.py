"""
Commandes applicatives : génération et édition des bulletins de paie.
Les routers appellent exclusivement ce module (jamais documents/ ou engine directement).
"""

from __future__ import annotations

from typing import Any


from app.shared.domain.employment_rules import is_forfait_jour as is_forfait_jour


def process_payslip_generation(
    employee_id: str, year: int, month: int, *, bac_a_sable: Any = None
) -> dict[str, Any]:
    """Génère une fiche de paie (heures). Délègue à documents.payslip_generator."""
    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation as _impl,
    )

    extra = {"bac_a_sable": bac_a_sable} if bac_a_sable is not None else {}
    return _impl(employee_id=employee_id, year=year, month=month, **extra)


def process_payslip_generation_forfait(
    employee_id: str, year: int, month: int, *, bac_a_sable: Any = None
) -> dict[str, Any]:
    """Génère une fiche de paie forfait jour. Délègue à documents.payslip_generator_forfait."""
    from app.modules.payroll.documents.payslip_generator_forfait import (
        process_payslip_generation_forfait as _impl,
    )

    extra = {"bac_a_sable": bac_a_sable} if bac_a_sable is not None else {}
    return _impl(employee_id=employee_id, year=year, month=month, **extra)
