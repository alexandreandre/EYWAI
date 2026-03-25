"""
Règles métier pures residence_permits : calcul du statut titre de séjour.

Logique déplacée depuis services.residence_permit_service.ResidencePermitService.
Aucune I/O, aucun FastAPI : uniquement datetime et constantes.
Comportement strictement identique au service legacy.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Optional

from app.modules.residence_permits.domain.enums import ResidencePermitStatus


# Seuil d'anticipation en jours (aligné sur le service legacy)
ANTICIPATION_THRESHOLD_DAYS = 45


def calculate_residence_permit_status(
    is_subject_to_residence_permit: bool,
    residence_permit_expiry_date: Optional[date],
    employment_status: str,
    reference_date: Optional[date] = None,
) -> Dict[str, object]:
    """
    Calcule le statut du titre de séjour selon les règles métier.

    Returns:
        dict avec : is_subject_to_residence_permit, residence_permit_status,
        residence_permit_expiry_date (str isoformat ou None), residence_permit_days_remaining,
        residence_permit_data_complete.
    """
    if reference_date is None:
        reference_date = date.today()

    # CAS 1: Employé non soumis
    if not is_subject_to_residence_permit:
        return {
            "is_subject_to_residence_permit": False,
            "residence_permit_status": None,
            "residence_permit_expiry_date": None,
            "residence_permit_days_remaining": None,
            "residence_permit_data_complete": None,
        }

    # CAS 2: Employé soumis mais statut d'emploi exclu du suivi (legacy renvoie la date telle quelle)
    if employment_status not in ("actif", "en_sortie"):
        return {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": None,
            "residence_permit_expiry_date": residence_permit_expiry_date,  # date | None
            "residence_permit_days_remaining": None,
            "residence_permit_data_complete": False,
        }

    # CAS 3: Employé soumis mais date d'expiration non renseignée
    if residence_permit_expiry_date is None:
        return {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": ResidencePermitStatus.TO_COMPLETE.value,
            "residence_permit_expiry_date": None,
            "residence_permit_days_remaining": None,
            "residence_permit_data_complete": False,
        }

    # CAS 4: Calcul du statut selon la date d'expiration
    days_remaining = (residence_permit_expiry_date - reference_date).days
    threshold_date = reference_date + timedelta(days=ANTICIPATION_THRESHOLD_DAYS)

    if residence_permit_expiry_date > threshold_date:
        status = ResidencePermitStatus.VALID.value
    elif residence_permit_expiry_date == reference_date:
        status = ResidencePermitStatus.TO_RENEW.value
    elif reference_date <= residence_permit_expiry_date <= threshold_date:
        status = ResidencePermitStatus.TO_RENEW.value
    elif residence_permit_expiry_date < reference_date:
        status = ResidencePermitStatus.EXPIRED.value
    else:
        status = ResidencePermitStatus.TO_COMPLETE.value

    return {
        "is_subject_to_residence_permit": True,
        "residence_permit_status": status,
        "residence_permit_expiry_date": residence_permit_expiry_date.isoformat(),
        "residence_permit_days_remaining": days_remaining,
        "residence_permit_data_complete": True,
    }
