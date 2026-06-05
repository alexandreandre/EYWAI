"""
Pont paie — heures de délégation CSE (rubrique DELEGATION_CSE).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def fetch_delegation_payroll_lines(
    company_id: str, year: int, month: int, employee_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Lignes paie pour imputation bulletin : heures de délégation du mois.
    Dépassements marqués is_overrun=True (traitement RH a posteriori).
    """
    from app.modules.cse.application.delegation_service import (
        get_payroll_delegation_entries,
    )

    return get_payroll_delegation_entries(company_id, year, month, employee_id)
