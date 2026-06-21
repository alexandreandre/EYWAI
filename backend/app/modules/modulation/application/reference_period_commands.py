"""Commands périodes de référence horaire."""

from __future__ import annotations

from typing import Any

from app.modules.modulation.domain.reference_period_rules import (
    period_from_row,
    validate_no_overlap,
)
from app.modules.modulation.infrastructure import work_time_periods_repository as repo


_WRITABLE = frozenset(
    {
        "label",
        "start_date",
        "end_date",
        "daily_reference_hours",
        "weekly_reference_hours",
        "affects_payroll",
        "affects_planning",
        "default_week_template_id",
        "is_active",
    }
)


def create_period(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    filtered = {k: v for k, v in payload.items() if k in _WRITABLE}
    if not filtered.get("daily_reference_hours") and not filtered.get("weekly_reference_hours"):
        raise ValueError("Renseignez les heures journalières ou hebdomadaires de référence.")
    candidate = period_from_row({"id": "new", "company_id": company_id, **filtered})
    existing = [period_from_row(r) for r in repo.list_periods(company_id, active_only=False)]
    validate_no_overlap(existing, candidate)
    return repo.upsert_period(company_id, filtered)


def update_period(
    company_id: str, period_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    row = repo.get_period(company_id, period_id)
    if not row:
        raise ValueError("Période introuvable.")
    filtered = {k: v for k, v in payload.items() if k in _WRITABLE and v is not None}
    merged = {**row, **filtered}
    candidate = period_from_row(merged)
    existing = [period_from_row(r) for r in repo.list_periods(company_id, active_only=False)]
    validate_no_overlap(existing, candidate, exclude_id=period_id)
    return repo.upsert_period(company_id, filtered, period_id=period_id)


def delete_period(company_id: str, period_id: str) -> None:
    if not repo.get_period(company_id, period_id):
        raise ValueError("Période introuvable.")
    repo.soft_delete_period(company_id, period_id)
