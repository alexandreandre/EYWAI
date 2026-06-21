"""Preset RH — modèle astreinte équipes (paramétrable après création)."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.payroll_variables.infrastructure import repository as repo

PRESET_BONUS_TYPES = [
    {
        "libelle": "Prime d'astreinte",
        "type": "montant_fixe",
        "montant": 176.18,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": "BPAS",
    },
    {
        "libelle": "Majoration astreinte samedi",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": "B_S0",
    },
    {
        "libelle": "Majoration astreinte dimanche",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": "B_VP",
    },
    {
        "libelle": "Indemnité km astreinte",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": False,
        "soumise_a_impot": False,
        "export_code": None,
    },
]

PRESET_RULES = [
    {
        "code": "astreinte_week",
        "label": "Prime d'astreinte hebdomadaire",
        "rule_type": "per_astreinte_week_tiered",
        "bonus_key": "Prime d'astreinte",
        "generation_mode": "suggest",
        "conditions": {
            "amount_normal": 176.18,
            "amount_christmas": 352.36,
            "amount_bridge": 250.0,
            "christmas_mode": "replace",
            "bridge_mode": "add",
            "christmas_detection": "iso_dec_25",
            "bridge_requires_astreinte_on_day": True,
        },
    },
    {
        "code": "astreinte_sat",
        "label": "Majoration astreinte samedi",
        "rule_type": "per_astreinte_weekend_majoration",
        "bonus_key": "Majoration astreinte samedi",
        "generation_mode": "suggest",
        "conditions": {
            "weekday_rates": {"5": 0.25},
            "min_hours": 1.0,
            "flat_hours": 1.0,
            "weekend_weekday_numbers": [5],
        },
    },
    {
        "code": "astreinte_sun",
        "label": "Majoration astreinte dimanche",
        "rule_type": "per_astreinte_weekend_majoration",
        "bonus_key": "Majoration astreinte dimanche",
        "generation_mode": "suggest",
        "conditions": {
            "weekday_rates": {"6": 1.0},
            "min_hours": 1.0,
            "flat_hours": 1.0,
            "weekend_weekday_numbers": [6],
        },
    },
    {
        "code": "astreinte_km",
        "label": "Indemnité km astreinte",
        "rule_type": "per_astreinte_weekend_km",
        "bonus_key": "Indemnité km astreinte",
        "generation_mode": "suggest",
        "conditions": {
            "km_free_threshold_one_way": 10,
            "round_trip_multiplier": 2,
            "requires_astreinte": True,
            "requires_weekend_work": True,
            "astreinte_link_mode": "same_iso_week",
            "quantity_mode": "once_if_eligible",
            "rate_mode": "coefficient_a",
            "vehicle_type_default": "voitures",
        },
    },
]


def _existing_bonus_by_label(company_id: str) -> dict[str, str]:
    resp = (
        supabase.table("company_bonus_types")
        .select("id, libelle")
        .eq("company_id", company_id)
        .execute()
    )
    return {str(r["libelle"]): str(r["id"]) for r in (resp.data or [])}


def _existing_rule_codes(company_id: str) -> set[str]:
    return {str(r["code"]) for r in repo.list_rules(company_id)}


def apply_astreinte_equipes_preset(company_id: str) -> dict[str, Any]:
    """Crée types de prime et règles manquants — n'écrase pas l'existant."""
    bonus_ids = _existing_bonus_by_label(company_id)
    created_bonuses: list[str] = []
    for spec in PRESET_BONUS_TYPES:
        label = spec["libelle"]
        if label in bonus_ids:
            continue
        row = {**spec, "company_id": company_id}
        resp = supabase.table("company_bonus_types").insert(row).execute()
        inserted = (resp.data or [row])[0]
        bonus_ids[label] = str(inserted["id"])
        created_bonuses.append(label)

    existing_codes = _existing_rule_codes(company_id)
    created_rules: list[str] = []
    sort_order = len(repo.list_rules(company_id))
    for spec in PRESET_RULES:
        code = spec["code"]
        if code in existing_codes:
            continue
        bonus_id = bonus_ids.get(spec["bonus_key"])
        rule_row = {
            "code": code,
            "label": spec["label"],
            "enabled": True,
            "rule_type": spec["rule_type"],
            "bonus_type_id": bonus_id,
            "amount": None,
            "rate": None,
            "conditions": spec["conditions"],
            "generation_mode": spec["generation_mode"],
            "sort_order": sort_order,
        }
        repo.upsert_rule(company_id, rule_row)
        created_rules.append(code)
        sort_order += 1

    return {
        "created_bonus_types": created_bonuses,
        "created_rules": created_rules,
        "skipped_existing": len(PRESET_RULES) - len(created_rules),
    }
