"""Preset RH — variables paie équipes (paniers + prime nuit)."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.payroll_variables.infrastructure import repository as repo

PRESET_BONUS_TYPES = [
    {
        "libelle": "Indemnité panier repas",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": False,
        "soumise_a_impot": False,
        "export_code": None,
    },
    {
        "libelle": "Prime équipe de nuit",
        "type": "montant_fixe",
        "montant": 0,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "export_code": None,
    },
]

PRESET_RULES = [
    {
        "code": "panier_jour",
        "label": "Indemnité panier jour",
        "rule_type": "per_shift_type",
        "bonus_key": "Indemnité panier repas",
        "generation_mode": "auto",
        "conditions": {
            "shift_type_codes": ["MATIN", "APREM"],
            "catalog_prime_id": "indemnite_panier_repas",
        },
    },
    {
        "code": "panier_nuit",
        "label": "Indemnité panier nuit",
        "rule_type": "per_shift_type",
        "bonus_key": "Indemnité panier repas",
        "generation_mode": "auto",
        "conditions": {
            "shift_type_codes": ["NUIT"],
            "catalog_prime_id": "indemnite_panier_repas",
        },
    },
    {
        "code": "prime_nuit_equipe",
        "label": "Prime équipe de nuit",
        "rule_type": "per_shift_type",
        "bonus_key": "Prime équipe de nuit",
        "generation_mode": "auto",
        "conditions": {"shift_type_codes": ["NUIT"]},
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


def apply_shift_teams_payroll_preset(company_id: str) -> dict[str, Any]:
    """Crée types de prime et règles équipes — n'écrase pas l'existant."""
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
