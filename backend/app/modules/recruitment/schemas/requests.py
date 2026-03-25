# app/modules/recruitment/schemas/requests.py
"""
Schémas Pydantic entrée API du module recruitment (source de vérité migrée).
Comportement identique à l’ancien router api/routers/recruitment.py.
Pour utiliser : from app.modules.recruitment.schemas import JobCreate, ...
"""

from typing import List, Optional
from pydantic import BaseModel


class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = "draft"
    tags: Optional[list] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list] = None


class CandidateCreate(BaseModel):
    job_id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None


class CandidateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None


class MoveCandidateBody(BaseModel):
    stage_id: str
    rejection_reason: Optional[str] = None
    rejection_reason_detail: Optional[str] = None


class InterviewCreate(BaseModel):
    candidate_id: str
    interview_type: Optional[str] = "Entretien RH"
    scheduled_at: str
    duration_minutes: Optional[int] = 60
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    participant_user_ids: Optional[List[str]] = None


class InterviewUpdate(BaseModel):
    interview_type: Optional[str] = None
    scheduled_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None


class NoteCreate(BaseModel):
    candidate_id: str
    content: str


class OpinionCreate(BaseModel):
    candidate_id: str
    rating: str
    comment: Optional[str] = None


class HireCandidateBody(BaseModel):
    hire_date: str
    site: Optional[str] = None
    service: Optional[str] = None
    job_title: Optional[str] = None
    contract_type: Optional[str] = None
