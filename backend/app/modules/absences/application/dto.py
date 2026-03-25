"""
DTOs applicatifs — transfert entre infrastructure et couche application.

Utilisés par commands/queries et mappers (infrastructure).
"""
from dataclasses import dataclass
from datetime import date
from typing import Any, List, Optional, Union


@dataclass
class AbsenceRequestDto:
    """Demande d'absence (sortie repository / entrée réponses API)."""
    id: str
    employee_id: str
    company_id: Optional[str]
    type: str
    selected_days: List[date]
    status: str
    comment: Optional[str]
    attachment_url: Optional[str]
    filename: Optional[str]
    event_subtype: Optional[str]
    jours_payes: Optional[int]
    created_at: Optional[Any] = None
    manager_id: Optional[str] = None


@dataclass
class AbsenceBalanceDto:
    """Solde pour un type (CP, RTT, repos, événement familial, sans solde)."""
    type: str
    acquired: float
    taken: float
    remaining: Union[float, str]


@dataclass
class CalendarDayDto:
    """Jour du calendrier planifié."""
    jour: int
    type: str
    heures_prevues: float = 0.0


@dataclass
class EvenementFamilialDto:
    """Événement familial avec quota et solde (sortie IEvenementFamilialQuotaProvider)."""
    code: str
    libelle: str
    duree_jours: int
    type_jours: str
    quota: int
    solde_restant: int
    taken: int
    cycles_completed: int = 0


@dataclass
class SignedUploadResultDto:
    """Résultat création URL signée upload."""
    path: str
    signed_url: str
