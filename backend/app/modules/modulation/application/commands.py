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
    }
)


def update_modulation_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    filtered = {k: v for k, v in payload.items() if k in _WRITABLE_KEYS and v is not None}
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
    }
    return repo.upsert_week_template(company_id, data, template_id)


def delete_week_template(company_id: str, template_id: str) -> None:
    repo.delete_week_template(company_id, template_id)
