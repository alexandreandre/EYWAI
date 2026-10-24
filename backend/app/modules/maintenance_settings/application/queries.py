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
        paid_waiting_days_per_year=None,
        paid_waiting_min_seniority_months=12,
        maintain_working_days=False,
        maintain_parental_leave=False,
        deduire_ijss_sans_subrogation=True,
        bareme_convention=None,
        created_at=None,
        updated_at=None,
    )


#: Colonne ajoutée le 23/10/2026. Une ligne lue avant la migration ne la porte
#: pas : c'est une société qui existait, elle garde le calcul d'avant (false),
#: comme la migration le pose.
_CLE_DEDUIRE_IJSS = "deduire_ijss_sans_subrogation"


def get_maintenance_settings(company_id: str) -> MaintenanceSettings:
    """Retourne la config ou les valeurs par défaut si aucune ligne."""
    raw = maintenance_settings_repository.get_by_company(company_id)
    if not raw:
        return _defaults(company_id)
    if _CLE_DEDUIRE_IJSS not in raw:
        raw = {**raw, _CLE_DEDUIRE_IJSS: False}
    return MaintenanceSettings.model_validate(raw)
