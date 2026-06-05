"""Tests résolution grilles salariales par département."""

from __future__ import annotations

from app.modules.collective_agreements.rules.resolver import (
    departement_from_code_postal,
    resolve_salaires_minima,
)


class TestResolver:
    def test_departement_from_code_postal_metropole(self):
        assert departement_from_code_postal("77000") == "77"
        assert departement_from_code_postal("01000") == "1"

    def test_departement_from_code_postal_corse(self):
        assert departement_from_code_postal("20000") == "2A"

    def test_resolve_by_departement(self):
        rules = {
            "grilles_salaires": [
                {
                    "zone_type": "departemental",
                    "zone_libelle": "Seine-et-Marne",
                    "departements": ["77"],
                    "minima": [{"coefficient": 150, "valeur": 1782.0}],
                },
                {
                    "zone_type": "departemental",
                    "zone_libelle": "Hérault",
                    "departements": ["34"],
                    "minima": [{"coefficient": 150, "valeur": 1850.0}],
                },
            ]
        }
        minima = resolve_salaires_minima(rules, code_postal="77000")
        assert len(minima) == 1
        assert minima[0]["valeur"] == 1782.0

    def test_resolve_legacy_flat(self):
        rules = {
            "salaires_minima": [{"coefficient": 240, "valeur": 2500.0}],
        }
        minima = resolve_salaires_minima(rules, code_postal="75001")
        assert minima[0]["valeur"] == 2500.0

    def test_resolve_national_fallback(self):
        rules = {
            "grilles_salaires": [
                {
                    "zone_type": "national",
                    "zone_libelle": "National",
                    "departements": [],
                    "minima": [{"coefficient": 100, "valeur": 2000.0}],
                },
            ]
        }
        minima = resolve_salaires_minima(rules, code_postal="99999")
        assert minima[0]["valeur"] == 2000.0
