# app/modules/recruitment/domain/__init__.py
"""Domaine recruitment : entités, règles, interfaces."""
from app.modules.recruitment.domain.entities import Job, Candidate, PipelineStage, Interview
from app.modules.recruitment.domain.enums import StageType, OpinionRating
from app.modules.recruitment.domain.interfaces import (
    IRecruitmentSettingsReader,
    IJobRepository,
    ICandidateRepository,
    IPipelineStageRepository,
    ITimelineEventWriter,
    ITimelineEventReader,
    IEmployeeCreator,
    IDuplicateChecker,
    IParticipantChecker,
    IInterviewRepository,
    INoteRepository,
    IOpinionRepository,
)

__all__ = [
    "Job",
    "Candidate",
    "PipelineStage",
    "Interview",
    "StageType",
    "OpinionRating",
    "IRecruitmentSettingsReader",
    "IJobRepository",
    "ICandidateRepository",
    "IPipelineStageRepository",
    "ITimelineEventWriter",
    "ITimelineEventReader",
    "IEmployeeCreator",
    "IDuplicateChecker",
    "IParticipantChecker",
    "IInterviewRepository",
    "INoteRepository",
    "IOpinionRepository",
]
