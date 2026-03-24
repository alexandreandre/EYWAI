"""
Schémas Pydantic entrée API du module absences.

Migrés depuis schemas/absence.py — comportement identique.
"""
from datetime import date
from typing import List, Literal

from pydantic import BaseModel

AbsenceType = Literal[
    "conge_paye",
    "rtt",
    "sans_solde",
    "repos_compensateur",
    "evenement_familial",
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
]
AbsenceStatus = Literal["pending", "validated", "rejected", "cancelled"]


class AbsenceRequestCreate(BaseModel):
    """Schéma pour la création d'une demande d'absence par un employé."""

    employee_id: str
    type: AbsenceType
    # On reçoit maintenant une liste de jours au lieu d'un intervalle
    selected_days: List[date]
    comment: str | None = None
    attachment_url: str | None = None
    filename: str | None = None
    event_subtype: str | None = None  # Requis si type = evenement_familial (ex: mariage_salarie, deces_enfant)


class AbsenceRequestStatusUpdate(BaseModel):
    """Schéma pour la mise à jour du statut d'une demande."""

    status: AbsenceStatus
