"""
Types et statuts d'absence (domain).

Alignés avec les schémas API (schemas/requests.py) et l'enum PostgreSQL absence_type (migrations 50, 55).
"""

from typing import Literal

AbsenceType = Literal[
    "conge_paye",
    "rtt",
    "jtc",
    "sans_solde",
    "repos_compensateur",
    "recuperation_modulation",
    "evenement_familial",
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
]
AbsenceStatus = Literal["pending", "validated", "rejected", "cancelled"]

# Types d'arrêt nécessitant une attestation de salaire (règle domain).
SALARY_CERTIFICATE_ABSENCE_TYPES: tuple[str, ...] = (
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
)

# Types éligibles attestation / maintien IJSS (alignés sur l'attestation de salaire).
IJSS_ELIGIBLE_TYPES: frozenset[str] = frozenset(SALARY_CERTIFICATE_ABSENCE_TYPES)


def type_calendrier_projete(absence_type: str) -> str | None:
    """Type de jour que la VALIDATION de cette absence écrit au calendrier.

    Source unique pour la projection ET sa réciproque (restauration à
    l'annulation) : arrêts → 'arret_maladie', sinon le mapping partagé ;
    None pour les types qui n'écrivent jamais le calendrier (jtc, sans_solde…).
    """
    from app.shared.domain.absence_calendar import ABSENCE_TYPE_TO_CALENDAR_TYPE

    if absence_type in IJSS_ELIGIBLE_TYPES:
        return "arret_maladie"
    return ABSENCE_TYPE_TO_CALENDAR_TYPE.get(absence_type)
