"""Lecture paramètres maintien de salaire."""

from __future__ import annotations

from app.modules.maintenance_settings.infrastructure.repository import (
    maintenance_settings_repository,
)
from app.modules.maintenance_settings.schemas.responses import MaintenanceSettings


def _defaults(company_id: str) -> MaintenanceSettings:
    return MaintenanceSettings(
        id=None,
        company_id=company_id,
        apply_legal_maintenance=True,
        min_seniority_months=12,
        min_seniority_months_at_mp=3,
        employer_waiting_days=7,
        seniority_extension_enabled=False,
        remove_employer_waiting=False,
        annual_unique_waiting=False,
        maintain_100_percent=False,
        differentiated_at_illness=False,
        maintain_by_category=False,
        no_seniority_condition=False,
        custom_duration_days=None,
        subrogation_mode="when_maintien",
        provident_relay_days=None,
        provident_maintenance_rate=None,
        provident_cadre_only=True,
        created_at=None,
        updated_at=None,
    )


def get_maintenance_settings(company_id: str) -> MaintenanceSettings:
    """Retourne la config ou les valeurs par défaut si aucune ligne."""
    raw = maintenance_settings_repository.get_by_company(company_id)
    if not raw:
        return _defaults(company_id)
    return MaintenanceSettings.model_validate(raw)
