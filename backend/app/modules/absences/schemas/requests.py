"""
Schémas Pydantic entrée API du module absences.

Migrés depuis schemas/absence.py — comportement identique.
"""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, model_validator

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

ArretType = Literal[
    "maladie_simple",
    "accident_travail",
    "maladie_professionnelle",
    "accident_trajet",
    "mi_temps_therapeutique",
    "ald",
    "rechute_at",
    "arret_exceptionnel",
]

_ARRETS_TYPES_PRINCIPAUX = frozenset(
    {
        "arret_maladie",
        "arret_at",
        "arret_maladie_pro",
        "arret_maternite",
        "arret_paternite",
    }
)


class AbsenceRequestCreate(BaseModel):
    """Schéma pour la création d'une demande d'absence par un employé."""

    employee_id: str
    type: AbsenceType
    # On reçoit maintenant une liste de jours au lieu d'un intervalle
    selected_days: List[date]
    comment: str | None = None
    attachment_url: str | None = None
    filename: str | None = None
    event_subtype: str | None = (
        None  # Requis si type = evenement_familial (ex: mariage_salarie, deces_enfant)
    )
    arret_type: Optional[ArretType] = None

    @model_validator(mode="after")
    def arret_type_required_for_arrets(self) -> "AbsenceRequestCreate":
        if self.type in _ARRETS_TYPES_PRINCIPAUX and self.arret_type is None:
            raise ValueError(
                "Le type d'arrêt est obligatoire pour ce type d'absence (arrêt / congé pathologique)."
            )
        return self


class AbsenceRequestStatusUpdate(BaseModel):
    """Schéma pour la mise à jour du statut d'une demande."""

    status: AbsenceStatus
    subrogation_active: Optional[bool] = None


class SalaryCertificateTransmissionUpdate(BaseModel):
    """Marquage transmission attestation vers CPAM / Net-Entreprises."""

    transmitted_to_cpam: bool = True


class ManagerApprovalRequest(BaseModel):
    """Validation ou refus par le manager (étape avant RH)."""

    approved: bool
    rejection_reason: str | None = None
