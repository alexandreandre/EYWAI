"""
Tests d'intégration du repository collective_agreements.

Vérifie les opérations CRUD et métier (catalogue, assignations) avec un client
Supabase mocké. Pour des tests contre une DB de test réelle, fournir une fixture
supabase_client ou db_session pointant vers la DB de test (voir conftest.py :
fixture collective_agreements_db_client à ajouter si besoin).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.collective_agreements.domain.exceptions import NotFoundError, ValidationError
from app.modules.collective_agreements.infrastructure.repository import (
    CollectiveAgreementRepository,
)


@pytest.mark.integration
class TestCollectiveAgreementRepositoryListCatalog:
    """Repository.list_catalog."""

    def test_returns_empty_list_when_no_data(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.list_catalog()

        assert result == []
        mock_supabase.table.assert_called_with("collective_agreements_catalog")
        mock_supabase.table.return_value.select.return_value.eq.assert_called_with(
            "is_active", True
        )

    def test_returns_data_from_response(self):
        mock_supabase = MagicMock()
        chain = (
            mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value
        )
        chain.execute.return_value = MagicMock(
            data=[{"id": "agr-1", "name": "CC Syntec", "idcc": "1486"}]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.list_catalog()

        assert len(result) == 1
        assert result[0]["name"] == "CC Syntec"

    def test_applies_sector_and_search_when_provided(self):
        mock_supabase = MagicMock()
        select_chain = mock_supabase.table.return_value.select.return_value
        # Chaîne : eq(is_active) -> eq(sector) -> or_(search) -> order -> execute
        select_chain.eq.return_value.eq.return_value.or_.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        repo.list_catalog(sector="IT", search="Syntec", active_only=True)

        select_chain.eq.assert_any_call("is_active", True)
        select_chain.eq.return_value.eq.assert_called_once_with("sector", "IT")
        select_chain.eq.return_value.eq.return_value.or_.assert_called_once()


@pytest.mark.integration
class TestCollectiveAgreementRepositoryGetCatalogItem:
    """Repository.get_catalog_item."""

    def test_returns_none_when_not_found(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_catalog_item("agr-unknown")

        assert result is None

    def test_returns_item_when_found(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": "agr-1", "name": "CC", "idcc": "1486"}
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_catalog_item("agr-1")

        assert result["id"] == "agr-1"
        assert result["name"] == "CC"


@pytest.mark.integration
class TestCollectiveAgreementRepositoryGetCatalogItemRulesPath:
    """Repository.get_catalog_item_rules_path."""

    def test_returns_none_when_no_data(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_catalog_item_rules_path("agr-1")

        assert result is None

    def test_returns_path_when_present(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"rules_pdf_path": "/catalog/doc.pdf"}
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_catalog_item_rules_path("agr-1")

        assert result == "/catalog/doc.pdf"


@pytest.mark.integration
class TestCollectiveAgreementRepositoryGetClassificationsForAgreement:
    """Repository.get_classifications_for_agreement."""

    def test_raises_not_found_when_agreement_missing(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(NotFoundError) as exc_info:
            repo.get_classifications_for_agreement("agr-unknown")

        assert "Convention" in exc_info.value.message or "non trouvée" in exc_info.value.message

    @patch(
        "app.modules.collective_agreements.infrastructure.repository.get_classifications_for_idcc"
    )
    def test_calls_classifications_for_idcc_when_agreement_exists(
        self, mock_get_classifications
    ):
        mock_get_classifications.return_value = [{"level": "1", "label": "Cadre"}]
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": "agr-1", "idcc": "1486"}
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_classifications_for_agreement("agr-1")

        assert result == [{"level": "1", "label": "Cadre"}]
        mock_get_classifications.assert_called_once_with(mock_supabase, "1486")


@pytest.mark.integration
class TestCollectiveAgreementRepositoryCreateCatalogItem:
    """Repository.create_catalog_item."""

    def test_raises_validation_error_when_insert_returns_empty(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(ValidationError) as exc_info:
            repo.create_catalog_item(
                {"name": "CC", "idcc": "1486", "is_active": True}
            )

        assert "création" in exc_info.value.message.lower() or "échec" in exc_info.value.message.lower()

    def test_returns_created_row(self):
        mock_supabase = MagicMock()
        created = {"id": "new-id", "name": "CC", "idcc": "1486"}
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[created]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.create_catalog_item(
            {"name": "CC", "idcc": "1486", "is_active": True}
        )

        assert result == created
        mock_supabase.table.return_value.insert.assert_called_once()


@pytest.mark.integration
class TestCollectiveAgreementRepositoryUpdateCatalogItem:
    """Repository.update_catalog_item."""

    def test_raises_not_found_when_agreement_does_not_exist(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(NotFoundError):
            repo.update_catalog_item("agr-unknown", {"name": "X"})

    def test_raises_validation_error_when_data_empty(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"rules_pdf_path": None}
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(ValidationError) as exc_info:
            repo.update_catalog_item("agr-1", {})

        assert "donnée" in exc_info.value.message.lower() or "mettre à jour" in exc_info.value.message.lower()


@pytest.mark.integration
class TestCollectiveAgreementRepositoryDeleteCatalogItem:
    """Repository.delete_catalog_item."""

    def test_raises_not_found_when_nothing_deleted(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(NotFoundError):
            repo.delete_catalog_item("agr-unknown")

    def test_returns_true_when_deleted(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "agr-1"}]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.delete_catalog_item("agr-1")

        assert result is True


@pytest.mark.integration
class TestCollectiveAgreementRepositoryAssignUnassign:
    """Repository assign_to_company / unassign_from_company."""

    def test_assign_raises_validation_error_when_insert_fails(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(ValidationError):
            repo.assign_to_company("c1", "agr-1", "user-1")

    def test_assign_returns_assignment(self):
        mock_supabase = MagicMock()
        assignment = {"id": "a1", "company_id": "c1", "collective_agreement_id": "agr-1"}
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[assignment]
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.assign_to_company("c1", "agr-1", "user-1")

        assert result == assignment
        call_data = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_data["company_id"] == "c1"
        assert call_data["collective_agreement_id"] == "agr-1"
        assert call_data["assigned_by"] == "user-1"

    def test_unassign_raises_not_found_when_no_row_deleted(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        with pytest.raises(NotFoundError):
            repo.unassign_from_company("a1", "c1")


@pytest.mark.integration
class TestCollectiveAgreementRepositoryCheckAssignmentExists:
    """Repository.check_assignment_exists."""

    def test_returns_false_when_no_assignment(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.check_assignment_exists("c1", "agr-1")

        assert result is False

    def test_returns_true_when_assignment_exists(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": "a1"}
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.check_assignment_exists("c1", "agr-1")

        assert result is True


@pytest.mark.integration
class TestCollectiveAgreementRepositoryGetAgreementForChat:
    """Repository.get_agreement_for_chat."""

    def test_returns_none_when_not_found(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_agreement_for_chat("agr-unknown")

        assert result is None

    def test_returns_selected_fields(self):
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={
                "id": "agr-1",
                "name": "CC Syntec",
                "idcc": "1486",
                "description": "IT",
                "rules_pdf_path": "/catalog/doc.pdf",
            }
        )
        repo = CollectiveAgreementRepository(supabase_client=mock_supabase)

        result = repo.get_agreement_for_chat("agr-1")

        assert result["name"] == "CC Syntec"
        assert result["rules_pdf_path"] == "/catalog/doc.pdf"
        mock_supabase.table.return_value.select.assert_called_once_with(
            "id, name, idcc, description, rules_pdf_path"
        )
