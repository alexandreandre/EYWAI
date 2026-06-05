"""Tests fusion multi-chunks extraction CC."""

from __future__ import annotations

from app.modules.collective_agreements.rules.merge import merge_extraction_results


class TestExtractorMerge:
    def test_merge_dedupe_bareme(self):
        results = [
            {
                "idcc": "1486",
                "prime_anciennete": {
                    "bareme": [{"annees_min": 3, "taux": 0.03}],
                    "base_de_calcul": None,
                },
                "salaires_minima": [],
                "grilles_salaires": [],
                "confidence": "medium",
                "citations": [],
            },
            {
                "idcc": "1486",
                "prime_anciennete": {
                    "bareme": [
                        {"annees_min": 5, "taux": 0.04},
                        {"annees_min": 3, "taux": 0.035},
                    ],
                    "base_de_calcul": {
                        "methode": "salaire_minimum_conventionnel",
                        "valeur": 1.0,
                    },
                },
                "salaires_minima": [{"coefficient": 240, "valeur": 2500.0, "libelle": None}],
                "grilles_salaires": [],
                "confidence": "high",
                "citations": [{"article": "15", "extrait": "..."}],
            },
        ]
        doc = merge_extraction_results(results, idcc="1486")
        assert doc.prime_anciennete is not None
        bareme = doc.prime_anciennete.bareme
        assert len(bareme) == 2
        assert bareme[0].annees_min == 3
        assert bareme[0].taux == 0.035
        assert bareme[1].annees_min == 5
        assert len(doc.salaires_minima) == 1

    def test_merge_dedupe_minima_by_coefficient(self):
        results = [
            {
                "idcc": "1090",
                "prime_anciennete": None,
                "salaires_minima": [
                    {"coefficient": 150, "valeur": 2100.0, "libelle": "A"},
                    {"coefficient": 150, "valeur": 2150.0, "libelle": "B"},
                ],
                "grilles_salaires": [],
                "confidence": "high",
                "citations": [],
            },
        ]
        doc = merge_extraction_results(results, idcc="1090")
        assert len(doc.salaires_minima) == 1
        assert doc.salaires_minima[0].valeur == 2150.0

    def test_merge_grilles_by_zone(self):
        results = [
            {
                "idcc": "1597",
                "prime_anciennete": None,
                "salaires_minima": [],
                "grilles_salaires": [
                    {
                        "zone_type": "departemental",
                        "zone_libelle": "Seine-et-Marne",
                        "departements": ["77"],
                        "regions": [],
                        "date_effet": "2022-01-01",
                        "source_titre": "Accord 77",
                        "minima": [
                            {"coefficient": 150, "valeur": 1782.0, "libelle": None}
                        ],
                    }
                ],
                "confidence": "high",
                "citations": [],
            },
            {
                "idcc": "1597",
                "prime_anciennete": None,
                "salaires_minima": [],
                "grilles_salaires": [
                    {
                        "zone_type": "departemental",
                        "zone_libelle": "Hérault",
                        "departements": ["34"],
                        "regions": [],
                        "date_effet": "2022-01-01",
                        "source_titre": "Accord 34",
                        "minima": [
                            {"coefficient": 150, "valeur": 1850.0, "libelle": None}
                        ],
                    }
                ],
                "confidence": "high",
                "citations": [],
            },
        ]
        doc = merge_extraction_results(results, idcc="1597")
        assert len(doc.grilles_salaires) == 2
        zones = {g.zone_libelle for g in doc.grilles_salaires}
        assert "Seine-et-Marne" in zones
        assert "Hérault" in zones
