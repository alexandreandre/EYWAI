"""
Tests unitaires du service applicatif employee_exits (application/service.py).

Dépendances (ExitChecklistRepository, infrastructure.queries) mockées.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.service import (
    DEFAULT_CHECKLIST_ITEMS,
    create_default_checklist_sync,
    enrich_exit_with_documents_and_checklist,
)


pytestmark = pytest.mark.unit

EXIT_ID = "exit-svc-test"
COMPANY_ID = "company-svc-test"


class TestDefaultChecklistItems:
    """Constante DEFAULT_CHECKLIST_ITEMS."""

    def test_contains_expected_categories(self):
        """Les items par défaut couvrent les catégories métier (badge, matériel, accès, etc.)."""
        assert len(DEFAULT_CHECKLIST_ITEMS) >= 5
        codes = {item["item_code"] for item in DEFAULT_CHECKLIST_ITEMS}
        assert "badge_return" in codes
        assert "equipment_return" in codes
        assert "work_certificate" in codes or "final_settlement" in codes

    def test_each_item_has_required_fields(self):
        """Chaque item a item_code, item_label, item_category, is_required, display_order."""
        for item in DEFAULT_CHECKLIST_ITEMS:
            assert "item_code" in item
            assert "item_label" in item
            assert "item_category" in item
            assert "is_required" in item
            assert "display_order" in item


@patch("app.modules.employee_exits.infrastructure.repository.ExitChecklistRepository")
class TestCreateDefaultChecklistSync:
    """Service create_default_checklist_sync."""

    def test_calls_repo_create_many_with_items_for_exit(self, mock_repo_class):
        """Appelle le repository avec une entrée par item par défaut, exit_id et company_id renseignés."""
        mock_repo = MagicMock()
        mock_repo.create_many.return_value = []
        mock_repo_class.return_value = mock_repo
        sb = MagicMock()

        create_default_checklist_sync(EXIT_ID, COMPANY_ID, supabase_client=sb)

        mock_repo_class.assert_called_once_with(sb)
        mock_repo.create_many.assert_called_once()
        items_passed = mock_repo.create_many.call_args[0][0]
        assert len(items_passed) == len(DEFAULT_CHECKLIST_ITEMS)
        for i, item in enumerate(items_passed):
            assert item["exit_id"] == EXIT_ID
            assert item["company_id"] == COMPANY_ID
            assert item["item_code"] == DEFAULT_CHECKLIST_ITEMS[i]["item_code"]
            assert item["item_label"] == DEFAULT_CHECKLIST_ITEMS[i]["item_label"]

    def test_does_not_raise_when_repo_raises(self, mock_repo_class):
        """En cas d'erreur du repository, le service ne propage pas (log uniquement)."""
        mock_repo = MagicMock()
        mock_repo.create_many.side_effect = RuntimeError("DB error")
        mock_repo_class.return_value = mock_repo

        create_default_checklist_sync(EXIT_ID, COMPANY_ID, supabase_client=MagicMock())
        # Pas d'exception propagée
        mock_repo.create_many.assert_called_once()


@patch("app.modules.employee_exits.application.service.infra_queries")
class TestEnrichExitWithDocumentsAndChecklist:
    """Service enrich_exit_with_documents_and_checklist."""

    def test_delegates_to_infra_queries(self, mock_infra_queries):
        """Délègue à infrastructure.queries.enrich_exit_with_documents_and_checklist avec les mêmes arguments."""
        exit_record = {"id": EXIT_ID, "company_id": COMPANY_ID}
        sb = MagicMock()

        enrich_exit_with_documents_and_checklist(
            exit_record,
            signed_url_expiry_seconds=7200,
            supabase_client=sb,
        )

        mock_infra_queries.enrich_exit_with_documents_and_checklist.assert_called_once_with(
            exit_record,
            7200,
            sb,
        )

    def test_default_expiry_3600(self, mock_infra_queries):
        """Par défaut signed_url_expiry_seconds vaut 3600."""
        exit_record = {"id": EXIT_ID}
        enrich_exit_with_documents_and_checklist(exit_record, supabase_client=MagicMock())
        call_args = mock_infra_queries.enrich_exit_with_documents_and_checklist.call_args[0]
        assert call_args[1] == 3600
