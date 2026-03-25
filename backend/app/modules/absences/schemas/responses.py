"""
Schémas Pydantic sortie API du module absences.

Migrés depuis schemas/absence.py — comportement identique.
"""

from datetime import date, datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.absences.schemas.requests import AbsenceStatus, AbsenceType


class AbsenceRequest(BaseModel):
    """Schéma représentant une demande d'absence complète depuis la BDD."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    created_at: datetime = Field(..., alias="created_at")
    employee_id: str
    type: AbsenceType
    # On remplace start_date et end_date par la liste des jours
    selected_days: List[date]
    comment: str | None
    status: AbsenceStatus
    manager_id: str | None = None
    attachment_url: str | None = None
    filename: str | None = None
    event_subtype: str | None = None
    jours_payes: int | None = None  # Pour conge_paye: jours payés (reste = sans solde)


class SimpleEmployee(BaseModel):
    """Représentation simplifiée d'un employé pour l'imbrication."""

    id: str
    first_name: str
    last_name: str


class AbsenceBalance(BaseModel):
    """Représente le solde pour un type d'absence."""

    type: str
    acquired: float
    taken: float
    remaining: float | Literal["N/A", "selon événement"]


class AbsenceBalancesResponse(BaseModel):
    """La liste complète des soldes d'un employé."""

    balances: List[AbsenceBalance]


class CalendarDay(BaseModel):
    """Représente un jour dans le calendrier planifié."""

    jour: int
    type: str
    heures_prevues: float | None = None


class MonthlyCalendarResponse(BaseModel):
    """Représente les données d'un calendrier mensuel."""

    days: List[CalendarDay]


class AbsencePageData(BaseModel):
    """Regroupe toutes les données nécessaires pour la page d'absences de l'employé."""

    balances: List[AbsenceBalance]
    calendar_days: List[CalendarDay]
    history: List[AbsenceRequest]


class EvenementFamilialEvent(BaseModel):
    """Un événement familial avec son quota, solde restant et nombre de fois consommé entièrement."""

    code: str
    libelle: str
    duree_jours: int
    type_jours: str
    quota: int
    solde_restant: int
    taken: int
    cycles_completed: int = (
        0  # Nombre de fois que l'événement a été entièrement consommé
    )


class EvenementFamilialQuotaResponse(BaseModel):
    """Liste des événements familiaux disponibles pour l'employé."""

    events: List[EvenementFamilialEvent]


class SimpleEmployeeWithBalances(SimpleEmployee):
    """Représentation d'un employé avec ses soldes d'absence."""

    balances: List[AbsenceBalance]


class AbsenceRequestWithEmployee(AbsenceRequest):
    """Schéma d'une demande d'absence avec les détails ET soldes de l'employé."""

    employee: SimpleEmployeeWithBalances
    event_familial_cycles_consumed: int | None = (
        None  # Visible RH : nb fois cet événement consommé entièrement
    )


class SignedUploadURL(BaseModel):
    """Réponse URL signée pour upload d'un justificatif (POST /get-upload-url)."""

    path: str
    signedURL: str
