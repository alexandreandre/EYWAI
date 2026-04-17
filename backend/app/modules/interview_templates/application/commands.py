"""Commandes applicatives interview_templates."""

from app.modules.interview_templates.infrastructure.repository import (
    SupabaseInterviewTemplateRepository,
    interview_template_repository,
)
from app.modules.interview_templates.schemas.requests import (
    InterviewTemplateCreate,
    InterviewTemplateUpdate,
)
from app.modules.interview_templates.schemas.responses import InterviewTemplate


def create_template(
    company_id: str,
    data: InterviewTemplateCreate,
    created_by: str,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> InterviewTemplate:
    repo = repository or interview_template_repository
    return repo.create(company_id, data, created_by)


def update_template(
    template_id: str,
    company_id: str,
    data: InterviewTemplateUpdate,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> InterviewTemplate:
    repo = repository or interview_template_repository
    return repo.update(template_id, company_id, data)


def archive_template(
    template_id: str,
    company_id: str,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> None:
    repo = repository or interview_template_repository
    if repo.count_annual_reviews_using_template(template_id, company_id) > 0:
        raise ValueError(
            "Impossible d'archiver ce modèle : il est encore lié à au moins un entretien."
        )
    repo.archive(template_id, company_id)


def duplicate_template(
    template_id: str,
    company_id: str,
    created_by: str,
    repository: SupabaseInterviewTemplateRepository | None = None,
) -> InterviewTemplate:
    repo = repository or interview_template_repository
    return repo.duplicate(template_id, company_id, created_by)
