"""
Tests de câblage (wiring) du module collective_agreements.

Vérifie que l'injection des dépendances et le flux de bout en bout fonctionnent :
commands/queries -> service -> repository (et providers). Pas de modification du code applicatif.
"""

from unittest.mock import MagicMock

import pytest

from app.modules.collective_agreements.application import commands, queries
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
from app.modules.collective_agreements.infrastructure.repository import (
    CollectiveAgreementRepository,
)


pytestmark = pytest.mark.integration


class TestServiceFactory:
    """Factory get_collective_agreements_service et construction du service."""

    def test_get_collective_agreements_service_returns_service_instance(self):
        svc = get_collective_agreements_service()
        assert isinstance(svc, CollectiveAgreementsService)

    def test_service_has_repository_and_storage_initialized(self):
        svc = get_collective_agreements_service()
        assert svc._repo is not None
        assert svc._storage is not None
        assert svc._text_cache is not None
        assert svc._pdf_extractor is not None
        assert svc._chat is not None


class TestCommandsWiring:
    """Flux commandes -> service (avec service injecté mocké)."""

    def test_create_catalog_item_wires_to_service(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.create_catalog_item.return_value = {"id": "new-id"}
        from app.modules.collective_agreements.application.dto import CatalogCreateInput

        data = CatalogCreateInput(
            name="CC",
            idcc="1486",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
        )
        result = commands.create_catalog_item(
            data, is_super_admin=True, service=mock_svc
        )
        assert result["id"] == "new-id"
        mock_svc.create_catalog_item.assert_called_once_with(data, True)

    def test_assign_agreement_to_company_wires_to_service(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.assign_to_company.return_value = {"id": "assign-1"}
        result = commands.assign_agreement_to_company(
            company_id="c1",
            collective_agreement_id="agr-1",
            user_id="user-1",
            has_rh_access=True,
            service=mock_svc,
        )
        assert result["id"] == "assign-1"
        mock_svc.assign_to_company.assert_called_once_with(
            "c1", "agr-1", "user-1", True
        )


class TestQueriesWiring:
    """Flux queries -> service (avec service injecté mocké)."""

    def test_list_catalog_query_wires_to_service(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.list_catalog.return_value = [{"id": "agr-1", "name": "CC"}]
        result = queries.list_catalog_query(service=mock_svc)
        assert len(result) == 1
        assert result[0]["name"] == "CC"
        mock_svc.list_catalog.assert_called_once_with(
            sector=None, search=None, active_only=True
        )

    def test_get_catalog_item_query_wires_to_service(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_catalog_item.return_value = {"id": "agr-1", "name": "CC"}
        result = queries.get_catalog_item_query("agr-1", service=mock_svc)
        assert result["id"] == "agr-1"
        mock_svc.get_catalog_item.assert_called_once_with("agr-1")

    def test_ask_question_query_wires_to_service(self):
        from app.modules.collective_agreements.application.dto import QuestionOutput

        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.ask_question.return_value = QuestionOutput(
            answer="Réponse", agreement_name="CC Syntec"
        )
        result = queries.ask_question_query(
            agreement_id="agr-1",
            question="Congés ?",
            company_id="c1",
            has_rh_access=True,
            service=mock_svc,
        )
        assert result.agreement_name == "CC Syntec"
        mock_svc.ask_question.assert_called_once_with("agr-1", "Congés ?", "c1", True)


class TestServiceToRepositoryWiring:
    """Flux service -> repository (repository mocké)."""

    def test_list_catalog_delegates_to_repository(self):
        mock_repo = MagicMock(spec=CollectiveAgreementRepository)
        mock_repo.list_catalog.return_value = [
            {"id": "agr-1", "name": "CC", "rules_pdf_path": None}
        ]
        storage = MagicMock()
        storage.create_signed_url.return_value = None
        svc = CollectiveAgreementsService(
            repository=mock_repo,
            storage=storage,
        )

        result = svc.list_catalog()

        assert len(result) == 1
        assert result[0]["id"] == "agr-1"
        mock_repo.list_catalog.assert_called_once_with(
            sector=None, search=None, active_only=True
        )

    def test_get_upload_url_uses_domain_rule_and_storage(self):
        storage = MagicMock()
        storage.create_signed_upload_url.return_value = {
            "path": "catalog/2025-01-01-abc.pdf",
            "signedUrl": "https://upload.url",
        }
        svc = CollectiveAgreementsService(storage=storage)

        result = svc.get_upload_url("doc.pdf")

        assert result.path == "catalog/2025-01-01-abc.pdf"
        assert result.signed_url == "https://upload.url"
        storage.create_signed_upload_url.assert_called_once()
        call_path = storage.create_signed_upload_url.call_args[0][0]
        assert call_path.startswith("catalog/")
        assert call_path.endswith(".pdf")
