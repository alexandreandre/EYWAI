"""Résolution référence horaire effective (modulation + périodes + contrat)."""

from __future__ import annotations

from app.modules.modulation.application.payroll_hook import build_modulation_weekly_hours_map
from app.modules.modulation.domain.reference_period_rules import (
    WorkTimePeriod,
    build_effective_weekly_hours_map,
    period_from_row,
)
from app.modules.modulation.infrastructure import repository as mod_repo
from app.modules.modulation.infrastructure import work_time_periods_repository as periods_repo


def resolve_effective_weekly_hours_map(
    company_id: str,
    year: int,
    base_weekly_hours: float,
) -> dict[tuple[int, int], float]:
    """Carte ISO semaine → heures de référence effectives pour la paie."""
    settings = mod_repo.get_modulation_settings(company_id)
    modulation_map = (
        build_modulation_weekly_hours_map(settings, year) if settings.enabled else {}
    )
    period_rows = periods_repo.list_periods(company_id, active_only=True)
    periods = [
        period_from_row(r)
        for r in period_rows
        if r.get("affects_payroll")
    ]
    return build_effective_weekly_hours_map(
        year, float(base_weekly_hours), modulation_map or None, periods
    )


def list_work_time_periods(company_id: str) -> list[WorkTimePeriod]:
    return [period_from_row(r) for r in periods_repo.list_periods(company_id, active_only=False)]
