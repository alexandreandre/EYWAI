"""Commands modulation."""

from __future__ import annotations

from typing import Any

from app.modules.modulation.application import queries
from app.modules.modulation.infrastructure import repository as repo

_WRITABLE_KEYS = frozenset(
    {
        "enabled",
        "reference_period_months",
        "average_weekly_hours",
        "weekly_high_hours",
        "weekly_low_hours",
        "high_weeks_per_cycle",
        "low_weeks_per_cycle",
        "cycle_start_week_iso",
        "pay_smoothed",
        "weekly_cap_hours",
        "theoretical_annual_hours",
        "hour_account_enabled",
        "hs_franchise_hours_per_period",
        "hs_franchise_period",
        "max_account_balance_hours",
        "account_credit_source",
        "recovery_absence_enabled",
        "recovery_absence_enabled",
        "recovery_debit_timing",
        "hs_routing_policy",
    }
)

_ACCOUNT_POLICIES = frozenset({"account_all", "franchise", "manual"})


def _validate_settings_coherence(payload: dict[str, Any]) -> None:
    policy = payload.get("hs_routing_policy")
    hour_account = payload.get("hour_account_enabled")
    if policy in _ACCOUNT_POLICIES and hour_account is False:
        raise ValueError(
            "La politique de routage HS nécessite le compte d'heures activé."
        )


def update_modulation_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    filtered = {k: v for k, v in payload.items() if k in _WRITABLE_KEYS and v is not None}
    if filtered:
        existing = repo.get_modulation_settings(company_id)
        merged = {
            "hour_account_enabled": existing.hour_account_enabled,
            "hs_routing_policy": existing.hs_routing_policy,
            **filtered,
        }
        _validate_settings_coherence(merged)
    if "cycle_start_week_iso" in filtered and hasattr(
        filtered["cycle_start_week_iso"], "isoformat"
    ):
        filtered["cycle_start_week_iso"] = filtered[
            "cycle_start_week_iso"
        ].isoformat()
    settings = repo.upsert_modulation_settings(company_id, filtered)
    return queries._settings_to_response(company_id, settings).model_dump()


def save_week_template(
    company_id: str, payload: dict[str, Any], template_id: str | None = None
) -> dict[str, Any]:
    data = {
        "name": payload["name"],
        "weekly_hours": payload.get("weekly_hours", 35),
        "day_configs": payload.get("day_configs") or [],
        "modulation_tier": payload.get("modulation_tier") or "neutral",
        "is_active": payload.get("is_active", True),
        "team_id": payload.get("team_id"),
        "description": payload.get("description"),
    }
    return repo.upsert_week_template(company_id, data, template_id)


def delete_week_template(company_id: str, template_id: str) -> None:
    repo.delete_week_template(company_id, template_id)


_MODULATION_PRESETS: dict[str, dict[str, Any]] = {
    "standard": {
        "enabled": False,
        "hour_account_enabled": False,
        "hs_routing_policy": "pay_all",
        "pay_smoothed": False,
    },
    "metallurgie_hour_account": {
        "enabled": True,
        "reference_period_months": 12,
        "average_weekly_hours": 35.0,
        "weekly_high_hours": 37.0,
        "weekly_low_hours": 32.0,
        "high_weeks_per_cycle": 1,
        "low_weeks_per_cycle": 1,
        "pay_smoothed": True,
        "weekly_cap_hours": 44.0,
        "hour_account_enabled": True,
        "hs_franchise_hours_per_period": 14.0,
        "hs_franchise_period": "month",
        "hs_routing_policy": "franchise",
        "account_credit_source": "overtime_only",
        "recovery_absence_enabled": True,
        "recovery_debit_timing": "on_validation",
    },
    "hour_account_only": {
        "enabled": False,
        "hour_account_enabled": True,
        "hs_routing_policy": "account_all",
        "pay_smoothed": False,
        "recovery_absence_enabled": True,
        "recovery_debit_timing": "on_validation",
    },
}


def apply_modulation_preset(company_id: str, preset: str) -> dict[str, Any]:
    payload = _MODULATION_PRESETS.get(preset)
    if not payload:
        raise ValueError(f"Preset inconnu : {preset}")
    _validate_settings_coherence(payload)
    settings = repo.upsert_modulation_settings(company_id, payload)
    return queries._settings_to_response(company_id, settings).model_dump()
