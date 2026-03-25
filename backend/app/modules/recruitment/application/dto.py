# app/modules/recruitment/application/dto.py
"""
DTOs applicatifs recruitment.
Les commandes et requêtes retournent des dicts compatibles avec les schémas
responses (JobOut, CandidateOut, etc.) ; ces DTOs servent de référence pour
la structure des données en couche application.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class JobDto:
    """Job pour couche application."""
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
    candidate_count: int = 0


@dataclass
class CandidateDto:
    """Candidat pour couche application."""
    id: str
    company_id: str
    job_id: str
    first_name: str
    last_name: str
    current_stage_id: Optional[str] = None
    current_stage_name: Optional[str] = None
    current_stage_type: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_reason_detail: Optional[str] = None
    hired_at: Optional[str] = None
    employee_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


# Autres DTOs (PipelineStageDto, InterviewDto, NoteDto, OpinionDto, TimelineEventDto) à ajouter si besoin.
