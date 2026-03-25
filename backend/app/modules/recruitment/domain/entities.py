# app/modules/recruitment/domain/entities.py
"""
Entités du domaine recruitment — placeholders.
À enrichir lors de la migration (Job, Candidate, PipelineStage, Interview, Note, Opinion, TimelineEvent).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    """Offre / poste à pourvoir."""

    id: str
    company_id: str
    title: str
    status: str
    description: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    tags: Optional[list] = None
    created_by: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Candidate:
    """Candidat à un poste."""

    id: str
    company_id: str
    job_id: str
    first_name: str
    last_name: str
    current_stage_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_reason_detail: Optional[str] = None
    hired_at: Optional[str] = None
    employee_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class PipelineStage:
    """Étape du pipeline (ex. Premier appel, Entretien RH, Refusé, Recruté)."""

    id: str
    job_id: str
    company_id: str
    name: str
    position: int
    stage_type: str
    is_final: bool = False


@dataclass
class Interview:
    """Entretien planifié pour un candidat."""

    id: str
    company_id: str
    candidate_id: str
    interview_type: str
    scheduled_at: str
    duration_minutes: int
    status: str
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str = ""
