"""
Providers externes pour le dashboard.

Résidence / titres de séjour : adaptateur vers app.shared.infrastructure.residence_permit
pour IResidencePermitStatusCalculator (aucun import legacy).
"""
from __future__ import annotations

from typing import Any

from app.modules.dashboard.domain.interfaces import IResidencePermitStatusCalculator
from app.shared.infrastructure.residence_permit import calculate_residence_permit_status as _calc_status


class ResidencePermitCalculatorAdapter:
    """Adapte le calculateur partagé (app.shared) au port IResidencePermitStatusCalculator."""

    def calculate_residence_permit_status(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Any,
        employment_status: str,
        reference_date: Any = None,
    ) -> dict:
        return _calc_status(
            is_subject_to_residence_permit=is_subject_to_residence_permit,
            residence_permit_expiry_date=residence_permit_expiry_date,
            employment_status=employment_status,
            reference_date=reference_date,
        )


def get_residence_permit_calculator() -> IResidencePermitStatusCalculator:
    """Retourne l'implémentation du calculateur de statut titre de séjour."""
    return ResidencePermitCalculatorAdapter()
