"""Tests service extraction CC (mocké, sans réseau)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.collective_agreements.rules.service import CCRulesService


class TestCCRulesServiceBatch:
    @patch("app.modules.collective_agreements.rules.service.CCRulesExtractor")
    def test_extract_batch_priority_dry_run(self, mock_extractor_cls):
        mock_repo = MagicMock()
        mock_repo.list_catalog_by_idcc.return_value = {
            "id": "ag-1486",
            "idcc": "1486",
            "name": "Syntec",
            "rules_pdf_path": "path.pdf",
        }
        mock_repo.get_rules_by_idcc.return_value = None

        mock_agreements = MagicMock()
        mock_agreements.get_catalog_item.return_value = {
            "id": "ag-1486",
            "idcc": "1486",
            "name": "Syntec",
            "rules_pdf_path": "path.pdf",
        }
        mock_agreements._get_or_cache_pdf_text.return_value = "x" * 200

        service = CCRulesService(
            rules_repo=mock_repo,
            agreements_service=mock_agreements,
            extractor=mock_extractor_cls.return_value,
        )

        outcomes = service.extract_batch(priority_only=True, dry_run=True)
        assert len(outcomes) == 6
        assert all(
            o.idcc in {"1486", "1090", "1516", "2098", "0044", "0292"}
            for o in outcomes
        )
        mock_extractor_cls.return_value.extract_from_text.assert_not_called()

    @patch("app.modules.collective_agreements.rules.service.CCRulesExtractor")
    def test_extract_and_persist_success(self, mock_extractor_cls):
        from app.modules.collective_agreements.rules.schema import (
            CCRulesDocument,
            PalierAnciennete,
            PrimeAnciennete,
            RulesMeta,
        )

        mock_repo = MagicMock()
        mock_repo.get_rules_by_idcc.return_value = None
        mock_repo.upsert_rules.return_value = {"rules": {"idcc": "1486"}}
        mock_repo.log_extraction.return_value = {"id": "log-1"}

        doc = CCRulesDocument(
            idcc="1486",
            prime_anciennete=PrimeAnciennete(
                bareme=[PalierAnciennete(annees_min=3, taux=0.03)]
            ),
            meta=RulesMeta(
                extracted_at="2026-01-01T00:00:00Z",
                model="test",
                confidence="high",
            ),
        )
        mock_extractor_cls.return_value._model = "google/gemini-2.5-flash"
        mock_extractor_cls.return_value.extract_from_text.return_value = (doc, 1000, None)

        mock_agreements = MagicMock()
        mock_agreements.get_catalog_item.return_value = {
            "id": "ag-1486",
            "idcc": "1486",
            "name": "Syntec",
            "rules_pdf_path": "path.pdf",
        }
        mock_agreements._get_or_cache_pdf_text.return_value = "Article 15 prime d'ancienneté " * 50

        mock_storage = MagicMock()
        mock_storage.create_signed_url.return_value = "https://example.com/pdf"

        service = CCRulesService(
            rules_repo=mock_repo,
            agreements_service=mock_agreements,
            extractor=mock_extractor_cls.return_value,
            storage=mock_storage,
        )

        outcome = service.extract_and_persist_by_agreement_id("ag-1486")
        assert outcome.success
        assert outcome.idcc == "1486"
        mock_repo.upsert_rules.assert_called_once()
        mock_repo.log_extraction.assert_called_once()
