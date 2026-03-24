"""
Calcul du statut des titres de séjour.
Point d'entrée partagé : délègue aux règles domaine (residence_permits), sans services legacy.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.residence_permits.domain.rules import (
    calculate_residence_permit_status as _calculate_residence_permit_status,
)


def _to_optional_date(value: Optional[Any]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            s = value[:10] if len(value) >= 10 else value
            return date.fromisoformat(s)
        except (ValueError, TypeError):
            return None
    return None


def calculate_residence_permit_status(
    is_subject_to_residence_permit: bool,
    residence_permit_expiry_date: Optional[Any],
    employment_status: str,
    reference_date: Optional[Any] = None,
) -> Dict[str, Any]:
    """Calcule le statut du titre de séjour (même contrat que l'ancien ResidencePermitService)."""
    ref: Optional[date] = None
    if reference_date is not None:
        ref = _to_optional_date(reference_date)
    return _calculate_residence_permit_status(
        is_subject_to_residence_permit=is_subject_to_residence_permit,
        residence_permit_expiry_date=_to_optional_date(residence_permit_expiry_date),
        employment_status=employment_status,
        reference_date=ref,
    )
