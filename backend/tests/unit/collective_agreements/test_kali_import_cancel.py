"""Tests annulation import KALI."""

from unittest.mock import MagicMock

import pytest

from app.modules.collective_agreements.application.kali_import import (
    KaliImportService,
    _hash_text,
)
from app.modules.collective_agreements.application.kali_import_cancel import (
    KaliImportCancelled,
    is_cancel_requested,
    request_cancel_catalog_sync,
    request_cancel_idcc,
    reset_kali_import_cancel_state_for_tests,
)
from app.modules.collective_agreements.infrastructure.kali_client import (
    KaliConventionMeta,
    KaliFetchResult,
)
from app.modules.collective_agreements.rules.service import ExtractionOutcome


def _fetch_result(idcc: str = "3248") -> KaliFetchResult:
    meta = KaliConventionMeta(
        idcc=idcc,
        kalicont_id="KALICONT000012345678",
        title="CC Métallurgie",
        legifrance_url="https://www.legifrance.gouv.fr/conv_coll/id/KALICONT000012345678/",
    )
    return KaliFetchResult(
        meta=meta,
        full_text="# CC\n" + ("Article salaire.\n" * 20),
        character_count=400,
        sections_fetched=1,
        articles_fetched=1,
    )


@pytest.fixture(autouse=True)
def _reset_cancel_state():
    reset_kali_import_cancel_state_for_tests()
    yield
    reset_kali_import_cancel_state_for_tests()


class TestKaliImportCancel:
    def test_request_cancel_idcc(self):
        assert request_cancel_idcc("3248") is True
        assert is_cancel_requested(idcc="3248") is True
        assert is_cancel_requested(idcc="1486") is False

    def test_request_cancel_catalog_sync(self):
        request_cancel_catalog_sync()
        assert is_cancel_requested(idcc="1486") is True

    def test_import_by_idcc_cancelled_after_fetch(self):
        kali = MagicMock()

        def _fetch(idcc: str):
            request_cancel_idcc(idcc)
            return _fetch_result(idcc)

        kali.fetch_convention_text.side_effect = _fetch
        svc = KaliImportService(kali=kali)
        outcome = svc.import_by_idcc("3248")

        assert outcome.success is False
        assert outcome.cancelled is True
        kali.fetch_convention_text.assert_called_once()

    def test_import_by_idcc_cancelled_during_extraction(self):
        kali = MagicMock()
        kali.fetch_convention_text.return_value = _fetch_result()

        agreements = MagicMock()
        agreements.create_catalog_item.return_value = {
            "id": "agr-3248",
            "idcc": "3248",
            "name": "CC Métallurgie",
        }

        rules_repo = MagicMock()
        rules_repo.list_catalog_by_idcc.return_value = []
        rules_repo.get_rules_by_idcc.return_value = None

        rules_service = MagicMock()

        def _extract(*args, **kwargs):
            request_cancel_idcc("3248")
            return ExtractionOutcome(
                success=False,
                idcc="3248",
                agreement_id="agr-3248",
                cancelled=True,
                error="Annulé par l'utilisateur",
            )

        rules_service.extract_and_persist_from_text.side_effect = _extract

        svc = KaliImportService(
            kali=kali,
            agreements=agreements,
            text_cache=MagicMock(),
            rules_repo=rules_repo,
            rules_service=rules_service,
        )
        outcome = svc.import_by_idcc("3248", extract_rules=True)

        assert outcome.success is False
        assert outcome.cancelled is True

    def test_sync_active_catalog_stops_on_cancel(self):
        kali = MagicMock()

        def _fetch(idcc: str):
            if idcc == "1486":
                request_cancel_catalog_sync()
            return _fetch_result(idcc)

        kali.fetch_convention_text.side_effect = _fetch

        agreements = MagicMock()
        agreements.create_catalog_item.side_effect = [
            {"id": "agr-1486", "idcc": "1486", "name": "CC 1486"},
            {"id": "agr-1090", "idcc": "1090", "name": "CC 1090"},
        ]

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
            text_cache=MagicMock(),
            rules_repo=rules_repo,
            rules_service=rules_service,
        )

        outcomes = svc.sync_active_catalog(extract_rules=True)

        assert len(outcomes) == 1
        assert outcomes[0].cancelled is True
        assert kali.fetch_convention_text.call_count == 1

    def test_raise_if_cancelled(self):
        from app.modules.collective_agreements.application.kali_import_cancel import (
            raise_if_cancelled,
        )

        request_cancel_idcc("3248")
        with pytest.raises(KaliImportCancelled):
            raise_if_cancelled(idcc="3248")
