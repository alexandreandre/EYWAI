"""Fixtures figées de règles CC pour tests golden paie."""

from __future__ import annotations

from typing import Any, Dict

PRIORITY_IDCC_RULES: Dict[str, Dict[str, Any]] = {
    "1486": {
        "schema_version": 1,
        "idcc": "1486",
        "prime_anciennete": {
            "bareme": [
                {"annees_min": 3, "taux": 0.03},
                {"annees_min": 5, "taux": 0.04},
                {"annees_min": 10, "taux": 0.05},
            ],
            "base_de_calcul": {
                "methode": "salaire_minimum_conventionnel",
                "valeur": 1.0,
            },
        },
        "salaires_minima": [
            {"coefficient": 240, "valeur": 2500.0, "libelle": "Ingénieur 240"},
            {"coefficient": 275, "valeur": 2900.0, "libelle": "Ingénieur 275"},
        ],
    },
    "1090": {
        "schema_version": 1,
        "idcc": "1090",
        "prime_anciennete": {
            "bareme": [
                {"annees_min": 3, "taux": 0.03},
                {"annees_min": 6, "taux": 0.04},
            ],
            "base_de_calcul": {"methode": "pourcentage_salaire_de_base", "valeur": 1.0},
        },
        "salaires_minima": [
            {"coefficient": 150, "valeur": 2100.0},
        ],
    },
    "1516": {
        "schema_version": 1,
        "idcc": "1516",
        "salaires_minima": [
            {"coefficient": 120, "valeur": 1900.0},
            {"coefficient": 180, "valeur": 2300.0},
        ],
    },
    "2098": {
        "schema_version": 1,
        "idcc": "2098",
        "prime_anciennete": {
            "bareme": [{"annees_min": 5, "taux": 0.03}],
            "base_de_calcul": {"methode": "salaire_minimum_conventionnel", "valeur": 1.0},
        },
        "salaires_minima": [{"coefficient": 100, "valeur": 1800.0}],
    },
    "0044": {
        "schema_version": 1,
        "idcc": "0044",
        "prime_anciennete": {
            "bareme": [
                {"annees_min": 3, "taux": 0.02},
                {"annees_min": 5, "taux": 0.03},
                {"annees_min": 10, "taux": 0.04},
            ],
        },
        "salaires_minima": [{"coefficient": 200, "valeur": 2200.0}],
    },
    "0292": {
        "schema_version": 1,
        "idcc": "0292",
        "prime_anciennete": {
            "bareme": [
                {"annees_min": 3, "taux": 0.024},
                {"annees_min": 6, "taux": 0.048},
                {"annees_min": 9, "taux": 0.072},
                {"annees_min": 12, "taux": 0.096},
                {"annees_min": 15, "taux": 0.12},
            ],
            "base_de_calcul": {"methode": "pourcentage_salaire_de_base", "valeur": 1.0},
        },
        "salaires_minima": [{"coefficient": 150, "valeur": 1900.0}],
    },
    "1297": {
        "schema_version": 1,
        "idcc": "1297",
        "prime_anciennete": {
            "bareme": [
                {"annees_min": 3, "taux": 0.024},
                {"annees_min": 6, "taux": 0.048},
                {"annees_min": 9, "taux": 0.072},
                {"annees_min": 12, "taux": 0.096},
                {"annees_min": 15, "taux": 0.12},
            ],
            "base_de_calcul": {"methode": "pourcentage_salaire_de_base", "valeur": 1.0},
        },
        "salaires_minima": [{"coefficient": 150, "valeur": 1900.0}],
    },
}


def conventions_collectives_snapshot() -> Dict[str, Any]:
    return {f"idcc_{k}": v for k, v in PRIORITY_IDCC_RULES.items()}
