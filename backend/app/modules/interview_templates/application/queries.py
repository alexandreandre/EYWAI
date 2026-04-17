"""Queries applicatives interview_templates."""

from typing import List

from app.modules.interview_templates.infrastructure.repository import (
    SupabaseInterviewTemplateRepository,
    interview_template_repository,
)
from app.modules.interview_templates.schemas.responses import InterviewTemplate


def get_templates(
    company_id: str,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> List[InterviewTemplate]:
    """Liste les modèles de trames de l'entreprise."""
    repo = repository or interview_template_repository
    return repo.get_all(company_id)


def get_template(
    template_id: str,
    company_id: str,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> InterviewTemplate | None:
    """Détail d'un modèle."""
    repo = repository or interview_template_repository
    return repo.get_by_id(template_id, company_id)
