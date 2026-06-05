"""Tests seed officiel métallurgie 3248."""

from __future__ import annotations

from app.modules.collective_agreements.rules.diagnostics import payroll_grid_available_from_rules
from app.modules.collective_agreements.rules.schema import CCRulesDocument, document_to_engine_rules
from app.modules.collective_agreements.rules.seeds import get_seed
from app.modules.collective_agreements.rules.validator import validate_cc_rules


class TestMetallurgieSeed:
    def test_seed_has_18_classes(self):
        seed = get_seed("3248")
        assert seed is not None
        assert seed.grille is not None
        assert len(seed.grille.minima) == 18

    def test_seed_prime_has_taux_par_classe(self):
        seed = get_seed("3248")
        assert seed is not None
        assert seed.prime is not None
        assert seed.prime.taux_par_classe is not None
        assert seed.prime.taux_par_classe["1"] == 0.0145
        assert seed.prime.base_de_calcul is not None
        assert seed.prime.base_de_calcul.methode == "metallurgie_prime_anciennete"

    def test_seed_document_validates(self):
        seed = get_seed("3248")
        doc = CCRulesDocument(idcc="3248", grilles_salaires=[seed.grille])  # type: ignore[list-item]
        doc.prime_anciennete = seed.prime
        result = validate_cc_rules(doc, expected_idcc="3248")
        assert result.ok

    def test_seed_rules_enable_payroll_grid(self):
        seed = get_seed("3248")
        doc = CCRulesDocument(idcc="3248", grilles_salaires=[seed.grille])  # type: ignore[list-item]
        rules = document_to_engine_rules(doc)
        assert payroll_grid_available_from_rules(rules) is True
