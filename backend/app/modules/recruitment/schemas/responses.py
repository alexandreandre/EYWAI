# app/modules/recruitment/schemas/responses.py
"""
Schémas Pydantic sortie API du module recruitment (source de vérité migrée).
Comportement identique à l’ancien router api/routers/recruitment.py.
Pour utiliser : from app.modules.recruitment.schemas import JobOut, ...
"""
from typing import Optional
from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    company_id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    status: str
    tags: Optional[list] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    candidate_count: Optional[int] = 0


class PipelineStageOut(BaseModel):
    id: str
    job_id: str
    name: str
    position: int
    is_final: bool
    stage_type: str


class CandidateOut(BaseModel):
    id: str
    company_id: str
    job_id: str
    current_stage_id: Optional[str] = None
    current_stage_name: Optional[str] = None
    current_stage_type: Optional[str] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_reason_detail: Optional[str] = None
    hired_at: Optional[str] = None
    employee_id: Optional[str] = None
    created_at: str
    updated_at: str


class InterviewOut(BaseModel):
    id: str
    candidate_id: str
    interview_type: str
    scheduled_at: str
    duration_minutes: int
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: str
    summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    participants: Optional[list] = None


class NoteOut(BaseModel):
    id: str
    candidate_id: str
    content: str
    author_id: str
    author_first_name: Optional[str] = None
    author_last_name: Optional[str] = None
    created_at: str


class OpinionOut(BaseModel):
    id: str
    candidate_id: str
    rating: str
    comment: Optional[str] = None
    author_id: str
    author_first_name: Optional[str] = None
    author_last_name: Optional[str] = None
    created_at: str


class TimelineEventOut(BaseModel):
    id: str
    candidate_id: str
    event_type: str
    description: str
    metadata: Optional[dict] = None
    actor_id: Optional[str] = None
    actor_first_name: Optional[str] = None
    actor_last_name: Optional[str] = None
    created_at: str


class DuplicateWarning(BaseModel):
    type: str  # "candidate" or "employee"
    existing_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
