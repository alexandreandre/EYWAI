"""Schémas interview_templates."""

from .requests import (
    InterviewTemplateCreate,
    InterviewTemplateUpdate,
    TemplateQuestionCreate,
    TemplateSectionCreate,
)
from .responses import InterviewTemplate, TemplateQuestion, TemplateSection

__all__ = [
    "InterviewTemplate",
    "InterviewTemplateCreate",
    "InterviewTemplateUpdate",
    "TemplateQuestion",
    "TemplateQuestionCreate",
    "TemplateSection",
    "TemplateSectionCreate",
]
