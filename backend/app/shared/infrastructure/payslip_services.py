"""
Pont unique app/* vers la génération/édition de bulletins (app.modules.payroll.documents) et recalc COR.

Délègue à app.modules.payroll.documents pour payslip_generator, payslip_editor, forfait ;
recalcul COR via app.modules.repos_compensateur.application.service.
Import paresseux pour limiter le chargement.
"""

from __future__ import annotations

from typing import Any


def process_payslip_generation(
    employee_id: str, year: int, month: int, *, bac_a_sable: Any = None
) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_generator (comportement identique)."""
    from app.modules.payroll.documents.payslip_generator import (
        process_payslip_generation as _impl,
    )

    extra = {"bac_a_sable": bac_a_sable} if bac_a_sable is not None else {}
    return _impl(employee_id=employee_id, year=year, month=month, **extra)


def process_payslip_generation_forfait(
    employee_id: str, year: int, month: int, *, bac_a_sable: Any = None
) -> dict[str, Any]:
    """Délègue à app.modules.payroll.documents.payslip_generator_forfait (comportement identique)."""
    from app.modules.payroll.documents.payslip_generator_forfait import (
        process_payslip_generation_forfait as _impl,
    )

    extra = {"bac_a_sable": bac_a_sable} if bac_a_sable is not None else {}
    return _impl(employee_id=employee_id, year=year, month=month, **extra)


def recalculer_credits_repos_employe(
    employee_id: str, company_id: str, year: int
) -> int:
    """Délègue à app.modules.repos_compensateur.application.service (comportement identique à l’ancien recalc_service)."""
    from app.modules.repos_compensateur.application.service import (
        recalculer_credits_repos_employe as _impl,
    )

    return _impl(employee_id=employee_id, company_id=company_id, year=year)
