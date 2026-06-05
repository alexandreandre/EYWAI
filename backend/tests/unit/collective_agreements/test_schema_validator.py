"""Tests validateur règles CC."""

from __future__ import annotations

import pytest

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    PalierAnciennete,
    PrimeAnciennete,
    SalaireMinimum,
    parse_extraction_result,
)
from app.modules.collective_agreements.rules.validator import validate_cc_rules


class TestSchemaValidator:
    def test_parse_valid_extraction(self):
        raw = {
            "idcc": "1486",
            "prime_anciennete": {
                "bareme": [{"annees_min": 3, "taux": 0.03}],
                "base_de_calcul": {
                    "methode": "salaire_minimum_conventionnel",
                    "valeur": 1.0,
                },
            },
            "salaires_minima": [
                {"coefficient": 240, "valeur": 2500.0, "libelle": "N1"}
            ],
            "grilles_salaires": [],
            "confidence": "high",
            "citations": [{"article": "15", "extrait": "3 % après 3 ans"}],
        }
        doc = parse_extraction_result(raw)
        assert doc.idcc == "1486"
        assert doc.prime_anciennete is not None
        assert len(doc.prime_anciennete.bareme) == 1
        assert doc.salaires_minima[0].valeur == 2500.0

    def test_validate_ok(self):
        doc = CCRulesDocument(
            idcc="1486",
            prime_anciennete=PrimeAnciennete(
                bareme=[PalierAnciennete(annees_min=3, taux=0.03)]
            ),
            salaires_minima=[],
        )
        result = validate_cc_rules(doc, expected_idcc="1486")
        assert result.ok

    def test_validate_idcc_mismatch(self):
        doc = CCRulesDocument(idcc="1090", salaires_minima=[SalaireMinimum(coefficient=100, valeur=2000)])
        result = validate_cc_rules(doc, expected_idcc="1486")
        assert not result.ok
        assert any("idcc" in e for e in result.errors)

    def test_validate_empty_rules(self):
        doc = CCRulesDocument(idcc="1486")
        result = validate_cc_rules(doc, expected_idcc="1486")
        assert not result.ok

    def test_validate_bareme_not_croissant(self):
        doc = CCRulesDocument(
            idcc="1486",
            prime_anciennete=PrimeAnciennete(
                bareme=[
                    PalierAnciennete(annees_min=5, taux=0.03),
                    PalierAnciennete(annees_min=3, taux=0.04),
                ]
            ),
        )
        result = validate_cc_rules(doc, expected_idcc="1486")
        assert not result.ok
        assert any("croissant" in e for e in result.errors)

    def test_validate_taux_superieur_un(self):
        doc = CCRulesDocument(
            idcc="1486",
            prime_anciennete=PrimeAnciennete(
                bareme=[PalierAnciennete(annees_min=3, taux=1.5)]
            ),
        )
        result = validate_cc_rules(doc, expected_idcc="1486")
        assert not result.ok

    def test_invalid_methode_becomes_none(self):
        doc = parse_extraction_result(
            {
                "idcc": "1486",
                "prime_anciennete": {
                    "bareme": [],
                    "base_de_calcul": {"methode": "inconnue", "valeur": 1.0},
                },
                "salaires_minima": [],
                "grilles_salaires": [],
                "confidence": "low",
                "citations": [],
            }
        )
        assert doc.prime_anciennete is not None
        assert doc.prime_anciennete.base_de_calcul is not None
        assert doc.prime_anciennete.base_de_calcul.methode is None
        assert doc.prime_anciennete.base_de_calcul.valeur == 1.0

    def test_normalise_valeur_de_point(self):
        doc = parse_extraction_result(
            {
                "idcc": "3248",
                "prime_anciennete": {
                    "bareme": [{"annees_min": 3, "taux": 0.03}],
                    "base_de_calcul": {"methode": "valeur de point", "valeur": 6.5},
                },
                "salaires_minima": [],
                "grilles_salaires": [],
                "confidence": "medium",
                "citations": [],
            }
        )
        assert doc.prime_anciennete is not None
        assert doc.prime_anciennete.base_de_calcul is not None
        assert doc.prime_anciennete.base_de_calcul.methode == "valeur_du_point"

    def test_normalise_verbose_ia_methode_valeur_point_pourcentage(self):
        doc = parse_extraction_result(
            {
                "idcc": "3248",
                "prime_anciennete": {
                    "bareme": [{"annees_min": 3, "taux": 0.03}],
                    "base_de_calcul": {
                        "methode": "valeur de point multiplié par le taux en pourcentage",
                        "valeur": 5.83,
                    },
                },
                "salaires_minima": [],
                "grilles_salaires": [],
                "confidence": "high",
                "citations": [],
            }
        )
        assert doc.prime_anciennete is not None
        assert doc.prime_anciennete.base_de_calcul is not None
        assert doc.prime_anciennete.base_de_calcul.methode == "valeur_du_point"
        assert doc.prime_anciennete.base_de_calcul.valeur == 5.83
