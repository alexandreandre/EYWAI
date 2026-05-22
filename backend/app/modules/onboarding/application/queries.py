"""Lecture et création de checklists onboarding — délégation au repository."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.onboarding.infrastructure.repository import onboarding_repository


def get_checklist(employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    return onboarding_repository.get_checklist_by_employee(employee_id, company_id)


def get_or_create_checklist(employee_id: str, company_id: str) -> Dict[str, Any]:
    data = get_checklist(employee_id, company_id)
    if not data:
        data = onboarding_repository.create_checklist(employee_id, company_id)
    return data


def list_hub_summaries(
    company_id: str, lookback_days: int = 90
) -> Dict[str, Any]:
    return onboarding_repository.list_hub_summaries(company_id, lookback_days)
