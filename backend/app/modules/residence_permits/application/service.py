"""
Orchestration residence_permits : enrichissement des lignes avec le statut calculé.

Logique applicative déplacée depuis api/routers/residence_permits ( _enrich_with_residence_permit_status ).
Parsing des dates et mise à jour du dict ; le calcul du statut est délégué au port IResidencePermitStatusCalculator.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.modules.residence_permits.domain.interfaces import (
    IResidencePermitStatusCalculator,
)


def _parse_expiry_date(expiry_date_value: Any) -> Optional[date]:
    """
    Parse la date d'expiration depuis une ligne employé (str iso ou date).
    Comportement identique au router legacy.
    """
    if expiry_date_value is None:
        return None
    if isinstance(expiry_date_value, date):
        return expiry_date_value
    if isinstance(expiry_date_value, str):
        try:
            return date.fromisoformat(expiry_date_value)
        except (ValueError, TypeError):
            return None
    return None


def enrich_row_with_residence_permit_status(
    employee_data: Dict[str, Any],
    calculator: IResidencePermitStatusCalculator,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Enrichit les données employé avec le statut calculé du titre de séjour.
    Logique ex-router legacy ( _enrich_with_residence_permit_status ) ; comportement inchangé.
    """
    is_subject = employee_data.get("is_subject_to_residence_permit", False)
    expiry_date = _parse_expiry_date(employee_data.get("residence_permit_expiry_date"))
    employment_status = employee_data.get("employment_status", "actif")

    status_data = calculator.calculate_residence_permit_status(
        is_subject_to_residence_permit=is_subject,
        residence_permit_expiry_date=expiry_date,
        employment_status=employment_status,
        reference_date=reference_date,
    )
    result = dict(employee_data)
    result.update(status_data)
    return result
