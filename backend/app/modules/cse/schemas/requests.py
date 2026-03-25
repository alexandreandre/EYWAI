# app/modules/cse/schemas/requests.py
"""
Schémas de requête CSE (Create, Update, Add, Start, params).
Comportement identique à l'ancien schemas.cse.
"""

from datetime import date as date_type, datetime, time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Types littéraux utilisés par les schémas de requête
ElectedMemberRole = Literal[
    "titulaire", "suppleant", "secretaire", "tresorier", "autre"
]
MeetingType = Literal["ordinaire", "extraordinaire", "cssct", "autre"]
MeetingStatus = Literal["a_venir", "en_cours", "terminee"]
ParticipantRole = Literal["participant", "observateur"]
BDESDocumentType = Literal["bdes", "pv", "autre"]


# ============================================================================
# Élus CSE
# ============================================================================


class ElectedMemberCreate(BaseModel):
    """Schéma pour la création d'un élu CSE."""

    employee_id: str = Field(..., description="ID de l'employé élu")
    role: ElectedMemberRole = Field(
        ..., description="Rôle CSE (titulaire, suppléant, etc.)"
    )
    college: Optional[str] = Field(None, description="Collège électoral")
    start_date: date_type = Field(..., description="Date de début du mandat")
    end_date: date_type = Field(..., description="Date de fin du mandat")
    notes: Optional[str] = Field(None, description="Notes additionnelles")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: date_type, info) -> date_type:
        """Valide que la date de fin est après la date de début."""
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("La date de fin doit être après la date de début")
        return v


class ElectedMemberUpdate(BaseModel):
    """Schéma pour la mise à jour d'un élu CSE."""

    role: Optional[ElectedMemberRole] = None
    college: Optional[str] = None
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ============================================================================
# Réunions CSE
# ============================================================================


class MeetingCreate(BaseModel):
    """Schéma pour la création d'une réunion CSE."""

    title: str = Field(..., min_length=1, description="Titre de la réunion")
    meeting_date: date_type = Field(..., description="Date de la réunion")
    meeting_time: Optional[time] = Field(None, description="Heure de la réunion")
    location: Optional[str] = Field(None, description="Lieu physique ou lien visio")
    meeting_type: MeetingType = Field(..., description="Type de réunion")
    agenda: Optional[Dict[str, Any]] = Field(None, description="Ordre du jour (JSONB)")
    notes: Optional[Dict[str, Any]] = Field(
        None, description="Notes additionnelles (JSONB)"
    )
    participant_ids: Optional[List[str]] = Field(
        default_factory=list, description="Liste des IDs des participants (employés)"
    )


class MeetingUpdate(BaseModel):
    """Schéma pour la mise à jour d'une réunion CSE."""

    title: Optional[str] = None
    meeting_date: Optional[date_type] = None
    meeting_time: Optional[time] = None
    location: Optional[str] = None
    meeting_type: Optional[MeetingType] = None
    status: Optional[MeetingStatus] = None
    agenda: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None


class MeetingParticipantAdd(BaseModel):
    """Schéma pour ajouter des participants à une réunion."""

    employee_ids: List[str] = Field(
        ..., min_length=1, description="Liste des IDs des employés à ajouter"
    )
    role: ParticipantRole = Field("participant", description="Rôle des participants")


# ============================================================================
# Enregistrements
# ============================================================================


class RecordingConsent(BaseModel):
    """Schéma pour le consentement RGPD d'un participant."""

    employee_id: str = Field(..., description="ID de l'employé")
    consent_given: bool = Field(..., description="Consentement donné ou non")
    timestamp: Optional[datetime] = Field(None, description="Timestamp du consentement")


class RecordingStart(BaseModel):
    """Schéma pour démarrer un enregistrement."""

    consents: List[RecordingConsent] = Field(
        ..., min_length=1, description="Liste des consentements RGPD des participants"
    )

    @model_validator(mode="after")
    def validate_all_consents(self):
        """Valide que tous les participants ont donné leur consentement."""
        if not all(c.consent_given for c in self.consents):
            raise ValueError("Tous les participants doivent donner leur consentement")
        return self


# ============================================================================
# Heures de délégation
# ============================================================================


class DelegationHourCreate(BaseModel):
    """Schéma pour la création d'une heure de délégation."""

    employee_id: Optional[str] = None
    date: date_type
    duration_hours: float = Field(..., gt=0, description="Durée en heures")
    reason: str = Field(..., min_length=1, description="Motif de l'heure de délégation")
    meeting_id: Optional[str] = None


class DelegationQuotaCreate(BaseModel):
    """Schéma pour créer un quota de délégation."""

    collective_agreement_id: Optional[str] = Field(
        None, description="ID de la convention collective"
    )
    quota_hours_per_month: float = Field(
        ..., ge=0, description="Quota mensuel en heures"
    )
    notes: Optional[str] = None


# ============================================================================
# Documents BDES
# ============================================================================


class BDESDocumentCreate(BaseModel):
    """Schéma pour la création d'un document BDES."""

    title: str = Field(..., min_length=1, description="Titre du document")
    document_type: BDESDocumentType = Field(..., description="Type de document")
    year: Optional[int] = Field(None, description="Année du document")
    is_visible_to_elected: bool = Field(True, description="Visible pour les élus")
    description: Optional[str] = Field(None, description="Description du document")
    file_path: str = Field(
        ..., description="Chemin vers le fichier dans Supabase Storage"
    )


class BDESDocumentUpdate(BaseModel):
    """Schéma pour la mise à jour d'un document BDES."""

    title: Optional[str] = None
    document_type: Optional[BDESDocumentType] = None
    year: Optional[int] = None
    is_visible_to_elected: Optional[bool] = None
    description: Optional[str] = None


# ============================================================================
# Calendrier électoral
# ============================================================================


class ElectionCycleCreate(BaseModel):
    """Schéma pour la création d'un cycle électoral."""

    cycle_name: str = Field(..., min_length=1, description="Nom du cycle électoral")
    mandate_end_date: date_type = Field(
        ..., description="Date de fin du mandat précédent"
    )
    election_date: Optional[date_type] = Field(None, description="Date des élections")
    notes: Optional[Dict[str, Any]] = None


class ElectionTimelineStepCreate(BaseModel):
    """Schéma pour créer une étape de timeline électorale."""

    step_name: str = Field(..., min_length=1, description="Nom de l'étape")
    step_order: int = Field(..., ge=0, description="Ordre d'affichage")
    due_date: date_type = Field(..., description="Date butoir")
    notes: Optional[str] = None


# ============================================================================
# Exports
# ============================================================================


class ExportParams(BaseModel):
    """Schéma pour les paramètres d'export."""

    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    year: Optional[int] = None
    employee_ids: Optional[List[str]] = None
    format: Literal["excel", "pdf"] = "excel"


__all__ = [
    "ElectedMemberRole",
    "MeetingType",
    "MeetingStatus",
    "ParticipantRole",
    "BDESDocumentType",
    "ElectedMemberCreate",
    "ElectedMemberUpdate",
    "MeetingCreate",
    "MeetingUpdate",
    "MeetingParticipantAdd",
    "RecordingConsent",
    "RecordingStart",
    "DelegationHourCreate",
    "DelegationQuotaCreate",
    "BDESDocumentCreate",
    "BDESDocumentUpdate",
    "ElectionCycleCreate",
    "ElectionTimelineStepCreate",
    "ExportParams",
]
