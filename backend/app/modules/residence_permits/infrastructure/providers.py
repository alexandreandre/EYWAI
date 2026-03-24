"""
Providers residence_permits : implémentation des ports (calculateur de statut).

Utilise les règles métier du domain (domain.rules.calculate_residence_permit_status).
Adapte les entrées Any -> date pour le domain ; aucun appel au service legacy.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.modules.residence_permits.domain.interfaces import IResidencePermitStatusCalculator
from app.modules.residence_permits.domain.rules import calculate_residence_permit_status as domain_calculate


def _to_optional_date(value: Any) -> Optional[date]:
    """Convertit une valeur (str iso, date, ou autre) en date ou None pour le domain."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    return None


class DomainResidencePermitStatusCalculator(IResidencePermitStatusCalculator):
    """
    Implémentation du calculateur via les règles métier du domain.
    Comportement strictement identique au service legacy.
    """

    def calculate_residence_permit_status(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Optional[Any],
        employment_status: str,
        reference_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        expiry = _to_optional_date(residence_permit_expiry_date)
        ref = _to_optional_date(reference_date)
        return domain_calculate(
            is_subject_to_residence_permit=is_subject_to_residence_permit,
            residence_permit_expiry_date=expiry,
            employment_status=employment_status,
            reference_date=ref,
        )


_calculator: Optional[IResidencePermitStatusCalculator] = None


def get_residence_permit_status_calculator() -> IResidencePermitStatusCalculator:
    """Retourne le calculateur de statut (implémentation domain)."""
    global _calculator
    if _calculator is None:
        _calculator = DomainResidencePermitStatusCalculator()
    return _calculator
