# app/modules/recruitment/schemas/__init__.py
"""
Schémas API du module recruitment (requêtes / réponses) — source de vérité migrée.
Import de compatibilité : from app.modules.recruitment.schemas import JobOut, JobCreate, ...
"""

from app.modules.recruitment.schemas.requests import (
    ArchiveCandidateBody,
    JobCreate,
    JobUpdate,
    CandidateCreate,
    CandidateUpdate,
    MoveCandidateBody,
    InterviewCreate,
    InterviewUpdate,
    NoteCreate,
    OpinionCreate,
    HireCandidateBody,
    PipelineStageCreate,
    PipelineStageUpdate,
    PipelineStagesReorderBody,
)
from app.modules.recruitment.schemas.responses import (
    JobOut,
    PipelineStageOut,
    CandidateOut,
    InterviewOut,
    NoteOut,
    OpinionOut,
    TimelineEventOut,
    DuplicateWarning,
)

__all__ = [
    "ArchiveCandidateBody",
    "JobCreate",
    "JobUpdate",
    "CandidateCreate",
    "CandidateUpdate",
    "MoveCandidateBody",
    "InterviewCreate",
    "InterviewUpdate",
    "NoteCreate",
    "OpinionCreate",
    "HireCandidateBody",
    "PipelineStageCreate",
    "PipelineStageUpdate",
    "PipelineStagesReorderBody",
    "JobOut",
    "PipelineStageOut",
    "CandidateOut",
    "InterviewOut",
    "NoteOut",
    "OpinionOut",
    "TimelineEventOut",
    "DuplicateWarning",
]
