"""
Tests unitaires des requêtes employee_exits (application/queries.py).

Repositories et providers mockés ; pas de DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.application import queries


pytestmark = pytest.mark.unit

COMPANY_ID = "company-exit-test"
EXIT_ID = "exit-uuid-test"
EMPLOYEE_ID = "employee-uuid-test"
DOCUMENT_ID = "doc-uuid-test"


def _make_employee(company_id=COMPANY_ID):
    return {
        "id": EMPLOYEE_ID,
        "company_id": company_id,
        "first_name": "Jean",
        "last_name": "Dupont",
    }


def _make_exit_with_employee():
    return {
        "id": EXIT_ID,
        "company_id": COMPANY_ID,
        "employee_id": EMPLOYEE_ID,
        "exit_type": "demission",
        "status": "demission_recue",
        "employees": {
            "id": EMPLOYEE_ID,
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "j@test.com",
            "job_title": "Dev",
        },
    }


@patch("app.modules.employee_exits.application.queries.infra_get_employee_by_id")
class TestGetEmployeeCompanyId:
    """Query get_employee_company_id."""

    def test_returns_company_id_when_employee_found(self, mock_get_employee):
        mock_get_employee.return_value = _make_employee()
        result = queries.get_employee_company_id(
            EMPLOYEE_ID, supabase_client=MagicMock()
        )
        assert result == COMPANY_ID

    def test_raises_404_when_employee_not_found(self, mock_get_employee):
        mock_get_employee.return_value = None
        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.get_employee_company_id(EMPLOYEE_ID, supabase_client=MagicMock())
        assert exc_info.value.status_code == 404
        assert "Employé non trouvé" in exc_info.value.detail


@patch(
    "app.modules.employee_exits.application.queries.enrich_exit_with_documents_and_checklist"
)
@patch("app.modules.employee_exits.application.queries.EmployeeExitRepository")
class TestListEmployeeExits:
    """Query list_employee_exits."""

    def test_returns_enriched_list(self, mock_repo_class, mock_enrich):
        mock_repo = MagicMock()
        rows = [_make_exit_with_employee()]
        mock_repo.list.return_value = rows
        mock_repo_class.return_value = mock_repo

        result = queries.list_employee_exits(COMPANY_ID, supabase_client=MagicMock())

        assert len(result) == 1
        assert result[0]["id"] == EXIT_ID
        mock_enrich.assert_called_once()
        assert mock_enrich.call_args[0][0] == rows[0]
        assert mock_enrich.call_args[0][1] == 3600

    def test_passes_filters_to_repository(self, mock_repo_class, mock_enrich):
        mock_repo = MagicMock()
        mock_repo.list.return_value = []
        mock_repo_class.return_value = mock_repo

        queries.list_employee_exits(
            COMPANY_ID,
            status="demission_effective",
            exit_type="demission",
            employee_id=EMPLOYEE_ID,
            supabase_client=MagicMock(),
        )

        mock_repo.list.assert_called_once_with(
            COMPANY_ID,
            status="demission_effective",
            exit_type="demission",
            employee_id=EMPLOYEE_ID,
        )


@patch(
    "app.modules.employee_exits.application.queries.enrich_exit_with_documents_and_checklist"
)
@patch("app.modules.employee_exits.application.queries.EmployeeExitRepository")
class TestGetEmployeeExit:
    """Query get_employee_exit."""

    def test_returns_enriched_exit(self, mock_repo_class, mock_enrich):
        exit_record = _make_exit_with_employee()
        mock_repo = MagicMock()
        mock_repo.get_with_employee.return_value = exit_record
        mock_repo_class.return_value = mock_repo

        result = queries.get_employee_exit(
            EXIT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert result["id"] == EXIT_ID
        assert result["employee_id"] == EMPLOYEE_ID
        mock_enrich.assert_called_once()

    def test_raises_404_when_exit_not_found(self, mock_repo_class, mock_enrich):
        mock_repo = MagicMock()
        mock_repo.get_with_employee.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.get_employee_exit(EXIT_ID, COMPANY_ID, supabase_client=MagicMock())
        assert exc_info.value.status_code == 404
        assert "Sortie non trouvée" in exc_info.value.detail


@patch("app.modules.employee_exits.application.queries.get_indemnity_calculator")
@patch("app.modules.employee_exits.application.queries.EmployeeExitRepository")
class TestCalculateExitIndemnities:
    """Query calculate_exit_indemnities."""

    def test_returns_indemnities_and_updates_exit(
        self, mock_repo_class, mock_calc_class
    ):
        exit_data = _make_exit_with_employee()
        mock_repo = MagicMock()
        mock_repo.get_with_employee.return_value = exit_data
        mock_repo.update.return_value = {**exit_data, "calculated_indemnities": {}}
        mock_repo_class.return_value = mock_repo
        calculator = MagicMock()
        indemnities = {
            "total_gross_indemnities": 1000,
            "indemnite_conges": {"jours_restants": 5},
            "total_net_indemnities": 800,
        }
        calculator.calculate.return_value = indemnities
        mock_calc_class.return_value = calculator

        result = queries.calculate_exit_indemnities(
            EXIT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert result == indemnities
        mock_repo.update.assert_called_once()
        call_kw = mock_repo.update.call_args[0]
        assert call_kw[2].get("calculated_indemnities") == indemnities

    def test_raises_404_when_exit_not_found(self, mock_repo_class, mock_calc_class):
        mock_repo = MagicMock()
        mock_repo.get_with_employee.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.calculate_exit_indemnities(
                EXIT_ID, COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.queries.EmployeeExitRepository")
class TestGetDocumentUploadUrl:
    """Query get_document_upload_url."""

    def test_raises_404_when_exit_not_found(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.get_document_upload_url(
                EXIT_ID, COMPANY_ID, "file.pdf", supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404

    @patch("app.modules.employee_exits.application.queries.get_exit_storage_provider")
    def test_returns_upload_url_when_exit_exists(
        self, mock_storage_provider, mock_repo_class
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"id": EXIT_ID}
        mock_repo_class.return_value = mock_repo
        storage = MagicMock()
        storage.create_signed_upload_url.return_value = (
            "https://signed-upload.example/url"
        )
        mock_storage_provider.return_value = storage

        result = queries.get_document_upload_url(
            EXIT_ID, COMPANY_ID, "file.pdf", supabase_client=MagicMock()
        )

        assert result["upload_url"] == "https://signed-upload.example/url"
        assert "storage_path" in result
        assert "exits/" in result["storage_path"]
        assert result["expires_in"] == 3600


@patch("app.modules.employee_exits.application.queries.get_exit_storage_provider")
@patch("app.modules.employee_exits.application.queries.ExitDocumentRepository")
class TestListExitDocuments:
    """Query list_exit_documents."""

    def test_returns_documents_with_download_url(
        self, mock_doc_repo_class, mock_storage_provider
    ):
        mock_doc_repo = MagicMock()
        mock_doc_repo.list_by_exit.return_value = [
            {
                "id": DOCUMENT_ID,
                "storage_path": "exits/1/doc.pdf",
                "filename": "doc.pdf",
            },
        ]
        mock_doc_repo_class.return_value = mock_doc_repo
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://download.example/url"
        mock_storage_provider.return_value = storage

        result = queries.list_exit_documents(
            EXIT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert len(result) == 1
        assert result[0]["download_url"] == "https://download.example/url"
        assert result[0]["filename"] == "doc.pdf"


@patch("app.modules.employee_exits.application.queries.get_company_by_id")
@patch("app.modules.employee_exits.application.queries.get_employee_full")
@patch("app.modules.employee_exits.application.queries.build_document_data_from_exit")
@patch("app.modules.employee_exits.application.queries.get_exit_storage_provider")
@patch("app.modules.employee_exits.application.queries.ExitDocumentRepository")
@patch("app.modules.employee_exits.application.queries.EmployeeExitRepository")
class TestGetExitDocumentDetails:
    """Query get_exit_document_details."""

    def test_raises_404_when_document_not_found(
        self,
        mock_exit_repo_class,
        mock_doc_repo_class,
        mock_storage,
        mock_build,
        mock_emp_full,
        mock_company,
    ):
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = None
        mock_doc_repo_class.return_value = mock_doc_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.get_exit_document_details(
                EXIT_ID, DOCUMENT_ID, COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404
        assert "Document non trouvé" in exc_info.value.detail

    def test_returns_details_with_document_data_and_download_url(
        self,
        mock_exit_repo_class,
        mock_doc_repo_class,
        mock_storage,
        mock_build,
        mock_emp_full,
        mock_company,
    ):
        doc = {
            "id": DOCUMENT_ID,
            "exit_id": EXIT_ID,
            "storage_path": "exits/1/doc.pdf",
            "document_data": {"employee": {"first_name": "Jean"}},
        }
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = doc
        mock_doc_repo_class.return_value = mock_doc_repo
        storage = MagicMock()
        storage.create_signed_url.return_value = "https://download.example/url"
        mock_storage.return_value = storage

        result = queries.get_exit_document_details(
            EXIT_ID, DOCUMENT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert result["id"] == DOCUMENT_ID
        assert result["document_data"] == {"employee": {"first_name": "Jean"}}
        assert result["download_url"] == "https://download.example/url"
        assert result.get("version", 1) >= 1


@patch("app.modules.employee_exits.application.queries.ExitDocumentRepository")
class TestGetDocumentEditHistory:
    """Query get_document_edit_history."""

    def test_raises_404_when_document_not_found(self, mock_doc_repo_class):
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = None
        mock_doc_repo_class.return_value = mock_doc_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            queries.get_document_edit_history(
                EXIT_ID, DOCUMENT_ID, COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404

    def test_returns_history_with_version(self, mock_doc_repo_class):
        doc = {
            "id": DOCUMENT_ID,
            "version": 2,
            "manually_edited": True,
            "last_edited_by": "user-1",
            "last_edited_at": "2025-01-20T10:00:00Z",
        }
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = doc
        mock_doc_repo_class.return_value = mock_doc_repo

        result = queries.get_document_edit_history(
            EXIT_ID, DOCUMENT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert result["document_id"] == DOCUMENT_ID
        assert result["total_versions"] == 2
        assert len(result["history"]) == 1
        assert result["history"][0]["version"] == 2


@patch("app.modules.employee_exits.application.queries.ExitChecklistRepository")
class TestGetExitChecklist:
    """Query get_exit_checklist."""

    def test_returns_items_ordered_by_display_order(self, mock_repo_class):
        items = [
            {"id": "item-1", "item_code": "badge_return", "display_order": 0},
            {"id": "item-2", "item_code": "equipment_return", "display_order": 1},
        ]
        mock_repo = MagicMock()
        mock_repo.list_by_exit.return_value = items
        mock_repo_class.return_value = mock_repo

        result = queries.get_exit_checklist(
            EXIT_ID, COMPANY_ID, supabase_client=MagicMock()
        )

        assert len(result) == 2
        assert result[0]["item_code"] == "badge_return"
        mock_repo.list_by_exit.assert_called_once_with(EXIT_ID, COMPANY_ID)
