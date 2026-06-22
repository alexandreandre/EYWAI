"""Tests couche déterministe (parser + seed)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.collective_agreements.rules.deterministic import apply_deterministic_layer
from app.modules.collective_agreements.rules.diagnostics import payroll_grid_available_from_rules
from app.modules.collective_agreements.rules.schema import CCRulesDocument, document_to_engine_rules
from app.modules.collective_agreements.rules.service import CCRulesService


SAMPLE_SMH = """
Barème unique des salaires minima hiérarchiques 2025
A | 1 | 21 700 €
A | 2 | 21 850 €
B | 3 | 22 450 €
B | 4 | 23 400 €
C | 5 | 24 250 €
C | 6 | 25 550 €
D | 7 | 26 400 €
D | 8 | 28 450 €
E | 9 | 30 500 €
E | 10 | 33 700 €
F | 11 | 34 900 €
F | 12 | 36 700 €
G | 13 | 40 000 €
G | 14 | 43 900 €
H | 15 | 47 000 €
H | 16 | 52 000 €
I | 17 | 59 300 €
I | 18 | 68 000 €
"""


class TestDeterministicLayer:
    def test_apply_seed_when_no_ia_grille(self):
        doc = CCRulesDocument(idcc="3248")
        result = apply_deterministic_layer(
            doc, "texte sans barème", idcc="3248"
        )
        assert any(g.minima for g in result.grilles_salaires)
        assert len(result.grilles_salaires[0].minima) == 18
        rules = document_to_engine_rules(result)
        assert payroll_grid_available_from_rules(rules) is True

    def test_apply_parser_when_table_present(self):
        doc = CCRulesDocument(idcc="3248")
        result = apply_deterministic_layer(doc, SAMPLE_SMH, idcc="3248")
        assert len(result.grilles_salaires[0].minima) == 18
        assert result.grilles_salaires[0].date_effet == "2025"

    def test_service_applies_deterministic_after_ia(self):
        empty_doc = CCRulesDocument(idcc="3248")
        mock_extractor = MagicMock()
        mock_extractor.extract_from_text.return_value = (empty_doc, 100, None)
        mock_extractor._model = "test-model"

        svc = CCRulesService(extractor=mock_extractor)
        svc._agreements = MagicMock()
        svc._agreements.get_catalog_item.return_value = {
            "id": "agr-3248",
            "idcc": "3248",
        }
        svc._rules_repo = MagicMock()
        svc._rules_repo.get_rules_by_idcc.return_value = None
        svc._rules_repo.upsert_rules.return_value = {"rules": {}}
        svc._rules_repo.log_extraction.return_value = {"id": "log-1"}

        outcome = svc.extract_and_persist_from_text(
            "agr-3248",
            "x" * 150,
        )
        assert outcome.success is True
        persisted_rules = svc._rules_repo.upsert_rules.call_args.kwargs["rules"]
        assert payroll_grid_available_from_rules(persisted_rules) is True
