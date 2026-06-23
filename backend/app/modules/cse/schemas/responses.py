# app/modules/cse/schemas/responses.py
"""
Schémas de réponse CSE (Read, ListItem, Status, Base, Alert).
Comportement identique à l'ancien schemas.cse.
"""

from datetime import date as date_type, datetime, time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.cse.schemas.requests import (
    BDESDocumentType,
    ElectedMemberRole,
    MeetingType,
    MeetingStatus,
    ParticipantRole,
)

# Types littéraux supplémentaires pour les réponses
ElectionCycleStatus = Literal["in_progress", "completed"]
TimelineStepStatus = Literal["pending", "completed", "overdue"]


# ============================================================================
# Élus CSE
# ============================================================================


class ElectedMemberBase(BaseModel):
    """Schéma de base pour un élu CSE."""

    role: ElectedMemberRole
    college: Optional[str] = None
    start_date: date_type
    end_date: date_type
    is_active: bool = True
    notes: Optional[str] = None


class ElectedMemberRead(BaseModel):
    """Schéma pour la lecture complète d'un élu CSE."""

    id: str
    company_id: str
    employee_id: str
    role: ElectedMemberRole
    college: Optional[str] = None
    start_date: date_type
    end_date: date_type
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None

    class Config:
        from_attributes = True


class ElectedMemberListItem(BaseModel):
    """Schéma pour un item de la liste des élus."""

    id: str
    employee_id: str
    first_name: str
    last_name: str
    job_title: Optional[str] = None
    role: ElectedMemberRole
    college: Optional[str] = None
    start_date: date_type
    end_date: date_type
    is_active: bool
    days_remaining: Optional[int] = Field(
        None, description="Jours restants avant fin de mandat"
    )

    class Config:
        from_attributes = True


class ElectedMemberStatus(BaseModel):
    """Schéma pour le statut élu d'un employé."""

    is_elected: bool = Field(..., description="Indique si l'employé est élu actif")
    current_mandate: Optional[ElectedMemberRead] = Field(
        None, description="Mandat actuel si élu"
    )
    role: Optional[ElectedMemberRole] = Field(None, description="Rôle CSE actuel")


# ============================================================================
# Réunions CSE
# ============================================================================


class MeetingBase(BaseModel):
    """Schéma de base pour une réunion CSE."""

    title: str
    meeting_date: date_type
    meeting_time: Optional[time] = None
    location: Optional[str] = None
    meeting_type: MeetingType
    status: MeetingStatus = "a_venir"
    agenda: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None


class MeetingParticipantRead(BaseModel):
    """Schéma pour la lecture d'un participant."""

    meeting_id: str
    employee_id: str
    role: ParticipantRole
    invited_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    attended: bool = False

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None

    class Config:
        from_attributes = True


class MeetingRead(BaseModel):
    """Schéma pour la lecture complète d'une réunion CSE."""

    id: str
    company_id: str
    title: str
    meeting_date: date_type
    meeting_time: Optional[time] = None
    location: Optional[str] = None
    meeting_type: MeetingType
    status: MeetingStatus
    agenda: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None
    convocations_pdf_path: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    participants: Optional[List[MeetingParticipantRead]] = None
    participant_count: Optional[int] = None

    class Config:
        from_attributes = True


class MeetingListItem(BaseModel):
    """Schéma pour un item de la liste des réunions."""

    id: str
    title: str
    meeting_date: date_type
    meeting_time: Optional[time] = None
    location: Optional[str] = None
    meeting_type: MeetingType
    status: MeetingStatus
    participant_count: int = 0
    has_minutes: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Heures de délégation
# ============================================================================


class DelegationHourBase(BaseModel):
    """Schéma de base pour une heure de délégation."""

    date: date_type
    duration_hours: float
    reason: str
    meeting_id: Optional[str] = None


class DelegationHourRead(BaseModel):
    """Schéma pour la lecture d'une heure de délégation."""

    id: str
    company_id: str
    employee_id: str
    date: date_type
    duration_hours: float
    reason: str
    meeting_id: Optional[str] = None
    source: str = "propre"
    origin_month: Optional[date_type] = None
    created_by: Optional[str] = None
    created_at: datetime

    first_name: Optional[str] = None
    last_name: Optional[str] = None

    class Config:
        from_attributes = True


class DelegationQuotaRead(BaseModel):
    """Schéma pour le quota mensuel d'heures de délégation (calculé ou legacy)."""

    id: str
    company_id: str
    collective_agreement_id: Optional[str] = None
    quota_hours_per_month: float
    notes: Optional[str] = None
    collective_agreement_name: Optional[str] = None
    credit_base: Optional[float] = None
    monthly_cap: Optional[float] = None
    reference_headcount: Optional[int] = None
    role: Optional[str] = None

    class Config:
        from_attributes = True


class DelegationConfigRead(BaseModel):
    """Configuration délégation par entreprise (effectif figé)."""

    id: str
    company_id: str
    reference_headcount: int
    reference_date: date_type
    report_enabled: bool = True
    mutualisation_enabled: bool = True
    is_configured: bool = False
    current_headcount: int = 0


class DelegationCreditRead(BaseModel):
    """Détail du crédit et solde pour un élu et un mois."""

    employee_id: str
    year: int
    month: int
    role: str
    reference_headcount: int
    reference_date: Optional[date_type] = None
    credit_base: float
    reported_available: float
    transfers_in: float
    transfers_out: float
    monthly_cap: float
    available_hours: float
    consumed_hours: float
    remaining_hours: float
    overrun_hours: float
    is_near_limit: bool = False
    is_over_limit: bool = False
    warnings: List[str] = Field(default_factory=list)
    quota_hours_per_month: float = 0.0


class DelegationTransferRead(BaseModel):
    """Mutualisation d'heures entre élus."""

    id: str
    company_id: str
    period_year: int
    period_month: int
    from_employee_id: str
    to_employee_id: str
    hours: float
    employer_notified_at: Optional[date_type] = None
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime


class DelegationRequestRead(BaseModel):
    """Bon de délégation (prévu / réalisé)."""

    id: str
    company_id: str
    employee_id: str
    planned_date: date_type
    planned_hours: float
    reason: str
    status: str
    realized_hours: Optional[float] = None
    employer_notified_at: Optional[date_type] = None
    delegation_hour_id: Optional[str] = None
    created_at: datetime


class DelegationRegisterRow(BaseModel):
    """Ligne du registre annuel par élu."""

    employee_id: str
    first_name: str
    last_name: str
    year: int
    role: str
    theoretical_credit: float
    consumed: float
    reported_used: float
    mutualised_received: float
    mutualised_given: float
    overrun: float
    remaining_end_year: float


class DelegationSummary(BaseModel):
    """Schéma pour le récapitulatif des heures de délégation."""

    employee_id: str
    first_name: str
    last_name: str
    quota_hours_per_month: float
    consumed_hours: float
    remaining_hours: float
    period_start: date_type
    period_end: date_type
    credit_base: float = 0.0
    reported_available: float = 0.0
    transfers_in: float = 0.0
    transfers_out: float = 0.0
    monthly_cap: float = 0.0
    available_hours: float = 0.0
    overrun_hours: float = 0.0
    is_near_limit: bool = False
    is_over_limit: bool = False
    role: Optional[str] = None


# ============================================================================
# Documents BDES
# ============================================================================


class BDESDocumentBase(BaseModel):
    """Schéma de base pour un document BDES."""

    title: str
    document_type: BDESDocumentType
    year: Optional[int] = None
    is_visible_to_elected: bool = True
    description: Optional[str] = None


class BDESDocumentRead(BaseModel):
    """Schéma pour la lecture d'un document BDES."""

    id: str
    company_id: str
    title: str
    document_type: BDESDocumentType
    file_path: str
    year: Optional[int] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    is_visible_to_elected: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    published_by_name: Optional[str] = None
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================================
# Calendrier électoral
# ============================================================================


class ElectionCycleBase(BaseModel):
    """Schéma de base pour un cycle électoral."""

    cycle_name: str
    mandate_end_date: date_type
    election_date: Optional[date_type] = None
    status: ElectionCycleStatus = "in_progress"


class ElectionTimelineStepRead(BaseModel):
    """Schéma pour la lecture d'une étape de timeline."""

    id: str
    election_cycle_id: str
    step_name: str
    step_order: int
    due_date: date_type
    completed_at: Optional[datetime] = None
    status: TimelineStepStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ElectionCycleRead(BaseModel):
    """Schéma pour la lecture d'un cycle électoral."""

    id: str
    company_id: str
    cycle_name: str
    mandate_end_date: date_type
    election_date: Optional[date_type] = None
    status: ElectionCycleStatus
    results_pdf_path: Optional[str] = None
    minutes_pdf_path: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    timeline: Optional[List[ElectionTimelineStepRead]] = None
    days_until_mandate_end: Optional[int] = None

    class Config:
        from_attributes = True


CseStatus = Literal[
    "unknown",
    "not_required",
    "obligation_pending",
    "carence",
    "carence_expired",
    "elected",
]


class CompanyCseSettings(BaseModel):
    """Paramètres statut CSE entreprise."""

    model_config = ConfigDict(from_attributes=True)

    company_id: str
    cse_status: Literal[
        "unknown", "not_required", "obligation_pending", "carence", "elected"
    ] = "unknown"
    carence_pv_document_id: Optional[str] = None
    carence_valid_until: Optional[date_type] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ElectionAlert(BaseModel):
    """Schéma pour une alerte électorale."""

    cycle_id: str
    cycle_name: str
    mandate_end_date: date_type
    days_remaining: int
    alert_level: Literal["info", "warning", "critical"] = Field(
        ..., description="Niveau d'alerte selon les jours restants"
    )
    message: str = Field(..., description="Message d'alerte")


# ============================================================================
# Alertes
# ============================================================================


class MandateAlert(BaseModel):
    """Schéma pour une alerte de fin de mandat."""

    elected_member_id: str
    employee_id: str
    first_name: str
    last_name: str
    role: ElectedMemberRole
    end_date: date_type
    days_remaining: int
    months_remaining: float


# Références forward (Pydantic v2)
MeetingRead.model_rebuild()
ElectionCycleRead.model_rebuild()


__all__ = [
    "ElectionCycleStatus",
    "TimelineStepStatus",
    "ElectedMemberBase",
    "ElectedMemberRead",
    "ElectedMemberListItem",
    "ElectedMemberStatus",
    "MeetingBase",
    "MeetingParticipantRead",
    "MeetingRead",
    "MeetingListItem",
    "DelegationHourBase",
    "DelegationHourRead",
    "DelegationQuotaRead",
    "DelegationSummary",
    "BDESDocumentBase",
    "BDESDocumentRead",
    "ElectionCycleBase",
    "ElectionTimelineStepRead",
    "ElectionCycleRead",
    "ElectionAlert",
    "MandateAlert",
]
