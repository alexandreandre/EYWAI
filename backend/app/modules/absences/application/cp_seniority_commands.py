"""Commandes CP ancienneté."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.absences.application import cp_seniority_queries
from app.modules.absences.domain.cp_seniority_resolver import (
    LEWIS_AGREEMENT_RULES,
    METALLURGIE_3248_RULES,
    PLASTURGIE_0292_RULES,
)
from app.modules.absences.infrastructure import cp_seniority_repository as repo
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_leave_policy,
)

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

_METALLURGIE_PRESET_PAYLOAD = {
    "seniority_reference": "cp_period_end",
    "seniority_basis": "seniority_reference_date",
    "counting_unit": "ouvrable",
    "forfait_annual_days_default": 218,
    "forfait_reduction_enabled": True,
}


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
    elif preset in ("lewis_agreement", "metallurgie_idcc_3248"):
        rules = (
            METALLURGIE_3248_RULES
            if preset == "metallurgie_idcc_3248"
            else LEWIS_AGREEMENT_RULES
        )
        payload = {
            "enabled": True,
            "preset": preset,
            "rules": rules,
            **_METALLURGIE_PRESET_PAYLOAD,
        }
    else:
        raise ValueError(f"Preset inconnu : {preset}")
    settings = repo.upsert_cp_seniority_settings(company_id, payload)
    return cp_seniority_queries._settings_to_api(company_id, settings)


def validate_cp_seniority_grants(
    company_id: str,
    grant_year: int,
    *,
    validated_by: str | None = None,
) -> dict[str, Any]:
    """Valide en bloc les grants CP ancienneté pour l'année."""
    preview = cp_seniority_queries.list_cp_seniority_preview(company_id, grant_year)
    validated_count = 0
    for row in preview:
        repo.validate_cp_seniority_grant(
            company_id,
            row["employee_id"],
            grant_year,
            status="validated",
            validated_by=validated_by,
        )
        validated_count += 1
    return {
        "grant_year": grant_year,
        "validated_count": validated_count,
        "status": "validated",
    }


def override_cp_seniority_grant(
    company_id: str,
    employee_id: str,
    grant_year: int,
    days_granted: float,
    *,
    validated_by: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Correction manuelle RH d'un grant CP ancienneté."""
    existing = repo.get_cp_seniority_grant(employee_id, grant_year)
    snapshot = dict((existing or {}).get("calculation_snapshot") or {})
    snapshot["manual_override"] = True
    if note:
        snapshot["override_note"] = note
    snapshot["days_granted"] = days_granted
    row = repo.upsert_cp_seniority_grant(
        company_id,
        employee_id,
        grant_year,
        days_granted,
        (existing or {}).get("category_resolved"),
        float((existing or {}).get("seniority_years_at_ref") or 0),
        float((existing or {}).get("forfait_days_reduction") or 0),
        snapshot,
        status="overridden",
        validated_by=validated_by,
    )
    return row
