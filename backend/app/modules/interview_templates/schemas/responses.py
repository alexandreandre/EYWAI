"""Schémas de réponse pour les modèles de trames d'entretien."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.modules.annual_reviews.schemas.requests import InterviewType


class TemplateQuestion(BaseModel):
    id: str
    section_id: str
    label: str
    question_type: str
    options: Optional[Any] = None
    is_required: bool = False
    is_self_evaluation: bool = False
    position: int = 0

    class Config:
        from_attributes = True


class TemplateSection(BaseModel):
    id: str
    template_id: str
    title: str
    position: int = 0
    questions: List[TemplateQuestion] = Field(default_factory=list)

    class Config:
        from_attributes = True


class InterviewTemplate(BaseModel):
    id: str
    company_id: str
    name: str
    interview_type: InterviewType
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sections: List[TemplateSection] = Field(default_factory=list)

    class Config:
        from_attributes = True
