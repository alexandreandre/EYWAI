"""
Tests des requêtes applicatives collective_agreements.

Chaque query est testée avec un service mocké ; on vérifie que la query
délègue au service et retourne le résultat attendu.
"""

from unittest.mock import MagicMock


from app.modules.collective_agreements.application.queries import (
    list_catalog_query,
    get_catalog_item_query,
    get_classifications_query,
    get_upload_url_query,
    get_my_company_agreements_query,
    get_all_assignments_query,
    ask_question_query,
)
from app.modules.collective_agreements.application.dto import (
    QuestionOutput,
    UploadUrlOutput,
)
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
)


# --- list_catalog_query ---


class TestListCatalogQuery:
    """Query list_catalog_query."""

    def test_returns_list_from_service(self):
        expected = [{"id": "agr-1", "name": "CC Syntec", "idcc": "1486"}]
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.list_catalog.return_value = expected

        result = list_catalog_query(
            sector="Informatique", search=None, active_only=True, service=mock_svc
        )

        assert result == expected
        mock_svc.list_catalog.assert_called_once_with(
            sector="Informatique", search=None, active_only=True
        )

    def test_passes_active_only_false(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.list_catalog.return_value = []

        list_catalog_query(active_only=False, service=mock_svc)

        mock_svc.list_catalog.assert_called_once_with(
            sector=None, search=None, active_only=False
        )


# --- get_catalog_item_query ---


class TestGetCatalogItemQuery:
    """Query get_catalog_item_query."""

    def test_returns_item_when_found(self):
        expected = {"id": "agr-1", "name": "CC", "idcc": "1486"}
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_catalog_item.return_value = expected

        result = get_catalog_item_query("agr-1", service=mock_svc)

        assert result == expected
        mock_svc.get_catalog_item.assert_called_once_with("agr-1")

    def test_returns_none_when_not_found(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_catalog_item.return_value = None

        result = get_catalog_item_query("agr-unknown", service=mock_svc)

        assert result is None


# --- get_classifications_query ---


class TestGetClassificationsQuery:
    """Query get_classifications_query."""

    def test_returns_classifications_list(self):
        expected = [{"level": "1", "label": "Cadre"}, {"level": "2", "label": "ETAM"}]
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_classifications.return_value = expected

        result = get_classifications_query("agr-1", service=mock_svc)

        assert result == expected
        mock_svc.get_classifications.assert_called_once_with("agr-1")


# --- get_upload_url_query ---


class TestGetUploadUrlQuery:
    """Query get_upload_url_query."""

    def test_returns_upload_url_output(self):
        out = UploadUrlOutput(path="catalog/doc.pdf", signed_url="https://signed.url")
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_upload_url.return_value = out

        result = get_upload_url_query("regles.pdf", service=mock_svc)

        assert result.path == "catalog/doc.pdf"
        assert result.signed_url == "https://signed.url"
        mock_svc.get_upload_url.assert_called_once_with("regles.pdf")


# --- get_my_company_agreements_query ---


class TestGetMyCompanyAgreementsQuery:
    """Query get_my_company_agreements_query."""

    def test_returns_assignments_list(self):
        expected = [
            {"id": "a1", "company_id": "c1", "agreement_details": {"name": "CC Syntec"}}
        ]
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_my_company_agreements.return_value = expected

        result = get_my_company_agreements_query(
            company_id="c1", has_rh_access=True, service=mock_svc
        )

        assert result == expected
        mock_svc.get_my_company_agreements.assert_called_once_with("c1", True)


# --- get_all_assignments_query ---


class TestGetAllAssignmentsQuery:
    """Query get_all_assignments_query."""

    def test_returns_all_assignments_by_company(self):
        expected = [
            {"id": "c1", "company_name": "Entreprise A", "assigned_agreements": []}
        ]
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.get_all_assignments.return_value = expected

        result = get_all_assignments_query(is_super_admin=True, service=mock_svc)

        assert result == expected
        mock_svc.get_all_assignments.assert_called_once_with(True)


# --- ask_question_query ---


class TestAskQuestionQuery:
    """Query ask_question_query."""

    def test_returns_question_output(self):
        out = QuestionOutput(answer="Selon l'article X...", agreement_name="CC Syntec")
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.ask_question.return_value = out

        result = ask_question_query(
            agreement_id="agr-1",
            question="Quelle est la durée des congés ?",
            company_id="c1",
            has_rh_access=True,
            service=mock_svc,
        )

        assert result.answer == "Selon l'article X..."
        assert result.agreement_name == "CC Syntec"
        mock_svc.ask_question.assert_called_once_with(
            "agr-1", "Quelle est la durée des congés ?", "c1", True
        )
