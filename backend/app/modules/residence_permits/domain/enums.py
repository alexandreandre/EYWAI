"""
Enums du domaine residence_permits.

Source unique dans le module. Le service legacy (services.residence_permit_service)
conserve une copie pour compatibilité (dashboard legacy, employees legacy, etc.).
"""

from enum import Enum


class ResidencePermitStatus(str, Enum):
    """Statuts possibles pour un titre de séjour."""

    VALID = "valid"
    TO_RENEW = "to_renew"
    EXPIRED = "expired"
    TO_COMPLETE = "to_complete"
