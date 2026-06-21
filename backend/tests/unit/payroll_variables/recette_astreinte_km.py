"""
Recette indemnité km astreinte — configuration de référence (groupe, pas de hardcode filiale).

À appliquer côté RH via l'UI entreprise + fiches salariés, puis valider en simulation dry-run.
"""

from __future__ import annotations

# Type de prime catalogue (company_bonus_types)
RECETTE_BONUS_TYPE = {
    "libelle": "Indemnité km astreinte",
    "type": "montant_fixe",
    "montant": 0,
    "soumise_a_cotisations": False,
    "soumise_a_impot": False,
}

# Règle variable (company_payroll_variable_rules)
RECETTE_RULE = {
    "code": "astreinte_km",
    "label": "Indemnité km astreinte",
    "rule_type": "per_astreinte_weekend_km",
    "enabled": True,
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
}

# Salariés exemples (employees.specificites_paie.deplacement_astreinte)
RECETTE_EMPLOYEES = [
    {"name": "JOUBERT", "distance_km_one_way": 22.2, "vehicle_cv": 7, "expected_eur": 17.01},
    {"name": "KOCIS", "distance_km_one_way": 15.4, "vehicle_cv": 4, "expected_eur": 6.55},
    {"name": "HAUCHECORNE", "distance_km_one_way": 35.0, "vehicle_cv": 4, "expected_eur": 30.30},
    {"name": "DUPONT", "distance_km_one_way": 1.0, "vehicle_cv": 4, "expected_skip": "below_threshold"},
]
