"""Schémas de requête pour les modèles de trames d'entretien."""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from app.modules.annual_reviews.schemas.requests import InterviewType

TemplateStatus = Literal["active", "archived"]

QuestionType = Literal[
    "text",
    "textarea",
    "number",
    "date",
    "boolean",
    "single_select",
    "multi_select",
]


class TemplateQuestionCreate(BaseModel):
    label: str
    question_type: QuestionType = "text"
    options: Optional[Any] = None
    is_required: bool = False
    is_self_evaluation: bool = False
    position: int = 0


class TemplateSectionCreate(BaseModel):
    title: str
    position: int = 0
    questions: List[TemplateQuestionCreate] = Field(default_factory=list)


class InterviewTemplateCreate(BaseModel):
    name: str
    interview_type: InterviewType
    sections: List[TemplateSectionCreate] = Field(default_factory=list)


class InterviewTemplateUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[TemplateStatus] = None
    sections: Optional[List[TemplateSectionCreate]] = None
