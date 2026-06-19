"""Commandes d’écriture maintien de salaire."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.maintenance_settings.application import queries
from app.modules.maintenance_settings.infrastructure.repository import (
    maintenance_settings_repository,
)
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate
from app.modules.maintenance_settings.schemas.responses import MaintenanceSettings

_DB_WRITABLE_KEYS = frozenset(
    {
        "apply_legal_maintenance",
        "min_seniority_months",
        "min_seniority_months_at_mp",
        "employer_waiting_days",
        "seniority_extension_enabled",
        "remove_employer_waiting",
        "annual_unique_waiting",
        "maintain_100_percent",
        "differentiated_at_illness",
        "maintain_by_category",
        "no_seniority_condition",
        "custom_duration_days",
        "subrogation_mode",
        "provident_relay_days",
        "provident_maintenance_rate",
        "provident_cadre_only",
    }
)


def save_maintenance_settings(
    company_id: str, data: MaintenanceSettingsUpdate
) -> MaintenanceSettings:
    """Fusionne avec l’existant, applique les règles métier, upsert."""
    current = queries.get_maintenance_settings(company_id)
    merged: Dict[str, Any] = current.model_dump(mode="json")
    patch = data.model_dump(exclude_unset=True)
    merged.update(patch)
    if merged.get("remove_employer_waiting"):
        merged["employer_waiting_days"] = 0

    payload = {k: merged[k] for k in _DB_WRITABLE_KEYS if k in merged}
    row = maintenance_settings_repository.upsert(company_id, payload)
    return MaintenanceSettings.model_validate(row)
