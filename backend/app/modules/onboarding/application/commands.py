"""Écritures onboarding — délégation au repository."""

from __future__ import annotations

from app.modules.onboarding.infrastructure.repository import onboarding_repository


def complete_task(
    task_id: str,
    checklist_id: str,
    company_id: str,
    user_id: str,
) -> bool:
    return onboarding_repository.complete_task(
        task_id, checklist_id, company_id, user_id
    )


def uncomplete_task(task_id: str, checklist_id: str, company_id: str) -> bool:
    return onboarding_repository.uncomplete_task(task_id, checklist_id, company_id)
