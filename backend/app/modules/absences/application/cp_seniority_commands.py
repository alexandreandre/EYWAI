"""Commandes CP ancienneté."""

from __future__ import annotations

from typing import Any

from app.modules.absences.application import cp_seniority_queries
from app.modules.absences.domain.cp_seniority import (
    LEWIS_AGREEMENT_RULES,
    PLASTURGIE_0292_RULES,
)
from app.modules.absences.infrastructure import cp_seniority_repository as repo

_WRITABLE_KEYS = frozenset(
    {
        "enabled",
        "preset",
        "seniority_reference",
        "seniority_basis",
        "counting_unit",
        "rules",
        "forfait_annual_days_default",
        "forfait_reduction_enabled",
        "company_agreement_overrides",
    }
)


def update_cp_seniority_settings(
    company_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    filtered = {k: v for k, v in payload.items() if k in _WRITABLE_KEYS and v is not None}
    if "rules" in filtered and hasattr(filtered["rules"], "model_dump"):
        filtered["rules"] = filtered["rules"].model_dump()
    settings = repo.upsert_cp_seniority_settings(company_id, filtered)
    return cp_seniority_queries._settings_to_api(company_id, settings)


def apply_cp_seniority_preset(company_id: str, preset: str) -> dict[str, Any]:
    if preset == "plasturgie_idcc_0292":
        payload = {
            "preset": "plasturgie_idcc_0292",
            "rules": PLASTURGIE_0292_RULES,
            "seniority_reference": "cp_period_end",
            "seniority_basis": "company_only",
            "counting_unit": "ouvrable",
            "forfait_annual_days_default": 216,
            "forfait_reduction_enabled": True,
        }
    elif preset == "lewis_agreement":
        payload = {
            "enabled": True,
            "preset": "lewis_agreement",
            "rules": LEWIS_AGREEMENT_RULES,
            "seniority_reference": "cp_period_end",
            "seniority_basis": "seniority_reference_date",
            "counting_unit": "ouvrable",
            "forfait_annual_days_default": 218,
            "forfait_reduction_enabled": True,
        }
    else:
        raise ValueError(f"Preset inconnu : {preset}")
    settings = repo.upsert_cp_seniority_settings(company_id, payload)
    return cp_seniority_queries._settings_to_api(company_id, settings)
