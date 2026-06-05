"""Tests unitaires import KALI → catalogue + cache texte."""

from unittest.mock import MagicMock

from app.modules.collective_agreements.application.kali_import import (
    KaliImportService,
    _hash_text,
)
from app.modules.collective_agreements.infrastructure.kali_client import (
    KaliConventionMeta,
    KaliFetchResult,
    PisteNotConfiguredError,
)
from app.modules.collective_agreements.rules.service import ExtractionOutcome


def _fetch_result(idcc: str = "1486") -> KaliFetchResult:
    meta = KaliConventionMeta(
        idcc=idcc,
        kalicont_id="KALICONT000012345678",
        title="CC Syntec",
        legifrance_url="https://www.legifrance.gouv.fr/conv_coll/id/KALICONT000012345678/",
    )
    return KaliFetchResult(
        meta=meta,
        full_text="# CC Syntec\nArticle 1\nContenu.",
        character_count=30,
        sections_fetched=1,
        articles_fetched=1,
    )


class TestKaliImportService:
    def test_import_by_idcc_success(self):
        kali = MagicMock()
        kali.fetch_convention_text.return_value = _fetch_result()

        agreements = MagicMock()
        agreements.create_catalog_item.return_value = {
            "id": "agr-1486",
            "idcc": "1486",
            "name": "CC Syntec",
        }
        agreements.update_catalog_item.return_value = None

        text_cache = MagicMock()
        rules_repo = MagicMock()
        rules_repo.list_catalog_by_idcc.return_value = []

        rules_service = MagicMock()
        rules_service.extract_and_persist_from_text.return_value = ExtractionOutcome(
            success=True,
            idcc="1486",
            agreement_id="agr-1486",
            rules={"idcc": "1486"},
            confidence="high",
        )

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=text_cache,
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcome = svc.import_by_idcc("1486", extract_rules=True)

        assert outcome.success is True
        assert outcome.agreement_id == "agr-1486"
        assert outcome.created is True
        assert outcome.character_count == 30
        text_cache.set_full_text.assert_called_once()
        args = text_cache.set_full_text.call_args
        assert args[0][0] == "agr-1486"
        assert args[1]["source_hash"] == "kali:KALICONT000012345678"
        rules_service.extract_and_persist_from_text.assert_called_once()

    def test_import_reextracts_when_text_unchanged(self):
        full_text = "# CC Syntec\nArticle 1\nContenu."
        text_hash = _hash_text(full_text)

        kali = MagicMock()
        kali.fetch_convention_text.return_value = KaliFetchResult(
            meta=_fetch_result().meta,
            full_text=full_text,
            character_count=len(full_text),
            sections_fetched=1,
            articles_fetched=1,
        )

        agreements = MagicMock()
        agreements.update_catalog_item.return_value = {
            "id": "agr-1486",
            "idcc": "1486",
            "name": "CC Syntec",
        }

        text_cache = MagicMock()
        rules_repo = MagicMock()
        rules_repo.list_catalog_by_idcc.return_value = {
            "id": "agr-1486",
            "idcc": "1486",
        }
        rules_repo.get_rules_by_idcc.return_value = {"source_text_hash": text_hash}

        rules_service = MagicMock()
        rules_service.extract_and_persist_from_text.return_value = ExtractionOutcome(
            success=True,
            idcc="1486",
            agreement_id="agr-1486",
        )

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=text_cache,
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcome = svc.import_by_idcc("1486", extract_rules=True)

        assert outcome.success is True
        assert outcome.text_changed is False
        assert outcome.rules_skipped is False
        rules_service.extract_and_persist_from_text.assert_called_once()

    def test_sync_skips_rules_when_text_unchanged(self):
        full_text = "# CC Syntec\nArticle 1\nContenu."
        text_hash = _hash_text(full_text)

        kali = MagicMock()
        kali.fetch_convention_text.return_value = KaliFetchResult(
            meta=_fetch_result().meta,
            full_text=full_text,
            character_count=len(full_text),
            sections_fetched=1,
            articles_fetched=1,
        )

        agreements = MagicMock()
        agreements.update_catalog_item.return_value = {
            "id": "agr-1486",
            "idcc": "1486",
            "name": "CC Syntec",
        }

        text_cache = MagicMock()
        rules_repo = MagicMock()
        rules_repo.list_catalog_by_idcc.return_value = {
            "id": "agr-1486",
            "idcc": "1486",
        }
        rules_repo.get_rules_by_idcc.return_value = {
            "source_text_hash": text_hash,
            "rules": {
                "grilles_salaires": [
                    {
                        "zone_type": "national",
                        "zone_libelle": "National",
                        "minima": [{"coefficient": 240, "valeur": 2500.0}],
                    }
                ],
            },
        }

        rules_service = MagicMock()

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=text_cache,
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcome = svc.import_by_idcc("1486", extract_rules=True)

        assert outcome.success is True
        assert outcome.text_changed is False
        assert outcome.rules_skipped is True
        rules_service.extract_and_persist_from_text.assert_not_called()

    def test_reextracts_when_rules_without_payroll_grid(self):
        full_text = "# CC Syntec\nArticle 1\nContenu."
        text_hash = _hash_text(full_text)

        kali = MagicMock()
        kali.fetch_convention_text.return_value = KaliFetchResult(
            meta=_fetch_result().meta,
            full_text=full_text,
            character_count=len(full_text),
            sections_fetched=1,
            articles_fetched=1,
        )

        agreements = MagicMock()
        agreements.update_catalog_item.return_value = {
            "id": "agr-3248",
            "idcc": "3248",
            "name": "CC Métallurgie",
        }

        text_cache = MagicMock()
        rules_repo = MagicMock()
        rules_repo.list_catalog_by_idcc.return_value = {
            "id": "agr-3248",
            "idcc": "3248",
        }
        rules_repo.get_rules_by_idcc.return_value = {
            "source_text_hash": text_hash,
            "rules": {
                "idcc": "3248",
                "prime_anciennete": {"bareme": [{"annees_min": 3, "taux": 0.03}]},
                "grilles_salaires": [],
                "salaires_minima": [],
            },
        }

        rules_service = MagicMock()
        rules_service.extract_and_persist_from_text.return_value = ExtractionOutcome(
            success=True,
            idcc="3248",
            agreement_id="agr-3248",
        )

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=text_cache,
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcome = svc.import_by_idcc("3248", extract_rules=True)

        assert outcome.success is True
        assert outcome.text_changed is False
        assert outcome.rules_skipped is False
        rules_service.extract_and_persist_from_text.assert_called_once()

    def test_sync_active_catalog(self):
        kali = MagicMock()
        kali.fetch_convention_text.side_effect = [
            _fetch_result("1486"),
            _fetch_result("1090"),
        ]

        agreements = MagicMock()
        agreements.create_catalog_item.side_effect = [
            {"id": "agr-1486", "idcc": "1486", "name": "CC 1486"},
            {"id": "agr-1090", "idcc": "1090", "name": "CC 1090"},
        ]

        text_cache = MagicMock()
        rules_repo = MagicMock()
        rules_repo.list_all_active_catalog.return_value = [
            {"id": "agr-1486", "idcc": "1486"},
            {"id": "agr-1090", "idcc": "1090"},
        ]
        rules_repo.list_catalog_by_idcc.return_value = None
        rules_repo.get_rules_by_idcc.return_value = None

        rules_service = MagicMock()
        rules_service.extract_and_persist_from_text.return_value = ExtractionOutcome(
            success=True,
            idcc="1486",
            agreement_id="agr-1486",
        )

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=text_cache,
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcomes = svc.sync_active_catalog(extract_rules=True)

        assert len(outcomes) == 2
        assert all(o.success for o in outcomes)
        assert kali.fetch_convention_text.call_count == 2

    def test_import_piste_not_configured(self):
        kali = MagicMock()
        kali.fetch_convention_text.side_effect = PisteNotConfiguredError("missing keys")

        svc = KaliImportService(kali=kali)
        outcome = svc.import_by_idcc("1486")

        assert outcome.success is False
        assert "missing keys" in (outcome.error or "")

    def test_get_text_source_kali(self):
        text_cache = MagicMock()
        text_cache.get_full_text.return_value = "texte"
        rules_repo = MagicMock()
        mock_table = MagicMock()
        rules_repo._supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.maybe_single.return_value = mock_table
        mock_table.execute.return_value = MagicMock(
            data={"pdf_hash": "kali:KALICONT123"}
        )

        svc = KaliImportService(text_cache=text_cache, rules_repo=rules_repo)
        assert svc.get_text_source("agr-1") == "kali"

    def test_get_text_source_missing(self):
        text_cache = MagicMock()
        text_cache.get_full_text.return_value = None
        agreements = MagicMock()
        agreements.get_catalog_item.return_value = {"rules_pdf_path": None}

        svc = KaliImportService(text_cache=text_cache, agreements=agreements)
        assert svc.get_text_source("agr-1") == "missing"
