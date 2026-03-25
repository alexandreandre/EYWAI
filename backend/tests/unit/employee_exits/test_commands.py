"""
Tests unitaires des commandes employee_exits (application/commands.py).

Repositories et providers mockés ; pas de DB ni HTTP.
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.commands import (
    add_checklist_item,
    create_employee_exit,
    create_exit_document,
    delete_checklist_item,
    delete_employee_exit,
    delete_exit_document,
    generate_exit_document,
    mark_checklist_item_complete,
    unpublish_exit_document,
    update_employee_exit,
    update_exit_status,
)
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError


pytestmark = pytest.mark.unit

COMPANY_ID = "company-exit-test"
EXIT_ID = "exit-uuid-test"
EMPLOYEE_ID = "employee-uuid-test"
USER_ID = "user-rh-test"


def _make_employee(company_id=COMPANY_ID, employment_status="actif"):
    return {
        "id": EMPLOYEE_ID,
        "company_id": company_id,
        "employment_status": employment_status,
        "first_name": "Jean",
        "last_name": "Dupont",
    }


def _make_exit_record(exit_id=EXIT_ID, status="demission_recue", exit_type="demission"):
    return {
        "id": exit_id,
        "company_id": COMPANY_ID,
        "employee_id": EMPLOYEE_ID,
        "exit_type": exit_type,
        "status": status,
        "exit_request_date": "2025-01-15",
        "last_working_day": "2025-03-15",
        "notice_period_days": 60,
        "is_gross_misconduct": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@patch("app.modules.employee_exits.application.commands.get_employee_by_id")
@patch("app.modules.employee_exits.application.commands.get_initial_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
@patch(
    "app.modules.employee_exits.application.commands.update_employee_employment_status"
)
@patch("app.modules.employee_exits.application.commands.create_default_checklist_sync")
@patch(
    "app.modules.employee_exits.application.commands._run_post_create_indemnities_and_docs"
)
class TestCreateEmployeeExit:
    """Commande create_employee_exit."""

    def test_creates_exit_when_employee_actif(
        self,
        mock_post_create,
        mock_checklist,
        mock_update_status,
        mock_repo_class,
        mock_initial_status,
        mock_get_employee,
    ):
        mock_get_employee.return_value = _make_employee()
        mock_initial_status.return_value = "demission_recue"
        mock_repo = MagicMock()
        created = _make_exit_record()
        created["id"] = EXIT_ID
        mock_repo.create.return_value = created
        mock_repo_class.return_value = mock_repo

        exit_data = {
            "employee_id": EMPLOYEE_ID,
            "exit_type": "demission",
            "exit_request_date": date(2025, 1, 15),
            "last_working_day": date(2025, 3, 15),
            "notice_period_days": 60,
            "is_gross_misconduct": False,
        }
        result = create_employee_exit(
            exit_data, COMPANY_ID, USER_ID, supabase_client=MagicMock()
        )

        assert result["id"] == EXIT_ID
        mock_repo.create.assert_called_once()
        mock_update_status.assert_called_once()
        assert mock_update_status.call_args[0][0] == EMPLOYEE_ID
        assert mock_update_status.call_args[0][1] == "en_sortie"
        assert mock_update_status.call_args[0][2] == EXIT_ID
        mock_checklist.assert_called_once()
        mock_post_create.assert_called_once()

    def test_raises_404_when_employee_not_found(
        self,
        mock_post_create,
        mock_checklist,
        mock_update_status,
        mock_repo_class,
        mock_initial_status,
        mock_get_employee,
    ):
        mock_get_employee.return_value = None

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            create_employee_exit(
                {
                    "employee_id": EMPLOYEE_ID,
                    "exit_type": "demission",
                    "exit_request_date": "2025-01-15",
                    "last_working_day": "2025-03-15",
                },
                COMPANY_ID,
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404
        assert "Employé non trouvé" in exc_info.value.detail

    def test_raises_400_when_employee_already_en_sortie(
        self,
        mock_post_create,
        mock_checklist,
        mock_update_status,
        mock_repo_class,
        mock_initial_status,
        mock_get_employee,
    ):
        mock_get_employee.return_value = _make_employee(employment_status="en_sortie")

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            create_employee_exit(
                {
                    "employee_id": EMPLOYEE_ID,
                    "exit_type": "demission",
                    "exit_request_date": "2025-01-15",
                    "last_working_day": "2025-03-15",
                },
                COMPANY_ID,
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "processus de sortie actif" in exc_info.value.detail

    def test_raises_404_when_employee_other_company(
        self,
        mock_post_create,
        mock_checklist,
        mock_update_status,
        mock_repo_class,
        mock_initial_status,
        mock_get_employee,
    ):
        mock_get_employee.return_value = _make_employee(company_id="other-company")

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            create_employee_exit(
                {
                    "employee_id": EMPLOYEE_ID,
                    "exit_type": "demission",
                    "exit_request_date": "2025-01-15",
                    "last_working_day": "2025-03-15",
                },
                COMPANY_ID,
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestUpdateEmployeeExit:
    """Commande update_employee_exit."""

    def test_returns_updated_exit(self, mock_repo_class):
        existing = _make_exit_record()
        updated = {**existing, "exit_reason": "Nouvelle raison"}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = updated
        mock_repo_class.return_value = mock_repo
        sb = MagicMock()

        result = update_employee_exit(
            EXIT_ID, COMPANY_ID, {"exit_reason": "Nouvelle raison"}, supabase_client=sb
        )
        assert result["exit_reason"] == "Nouvelle raison"

    def test_raises_404_when_exit_not_found(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            update_employee_exit(
                EXIT_ID, COMPANY_ID, {"exit_reason": "x"}, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404
        assert "Sortie non trouvée" in exc_info.value.detail

    def test_returns_existing_when_update_data_empty(self, mock_repo_class):
        existing = _make_exit_record()
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo_class.return_value = mock_repo

        result = update_employee_exit(
            EXIT_ID, COMPANY_ID, {}, supabase_client=MagicMock()
        )
        assert result == existing
        mock_repo.update.assert_not_called()


@patch(
    "app.modules.employee_exits.application.commands.update_employee_employment_status"
)
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestUpdateExitStatus:
    """Commande update_exit_status."""

    def test_raises_404_when_exit_not_found(self, mock_repo_class, mock_update_emp):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            update_exit_status(
                EXIT_ID,
                COMPANY_ID,
                "demission_effective",
                None,
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404

    def test_raises_400_on_invalid_transition(self, mock_repo_class, mock_update_emp):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _make_exit_record(
            status="demission_recue", exit_type="demission"
        )
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            update_exit_status(
                EXIT_ID,
                COMPANY_ID,
                "archivee",
                None,
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "Transition invalide" in exc_info.value.detail

    def test_success_valid_transition(self, mock_repo_class, mock_update_emp):
        existing = _make_exit_record(status="demission_recue", exit_type="demission")
        updated = {**existing, "status": "demission_preavis_en_cours"}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.return_value = updated
        mock_repo_class.return_value = mock_repo

        result = update_exit_status(
            EXIT_ID,
            COMPANY_ID,
            "demission_preavis_en_cours",
            None,
            USER_ID,
            supabase_client=MagicMock(),
        )
        assert result["status"] == "demission_preavis_en_cours"
        mock_repo.update.assert_called_once()


@patch(
    "app.modules.employee_exits.application.commands.get_exit_documents_storage_paths"
)
@patch("app.modules.employee_exits.application.commands.get_exit_storage_provider")
@patch(
    "app.modules.employee_exits.application.commands.update_employee_employment_status"
)
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestDeleteEmployeeExit:
    """Commande delete_employee_exit."""

    def test_deletes_exit_and_resets_employee_status(
        self, mock_repo_class, mock_update_emp, mock_storage_provider, mock_get_paths
    ):
        existing = _make_exit_record()
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo_class.return_value = mock_repo
        mock_get_paths.return_value = []
        mock_storage = MagicMock()
        mock_storage_provider.return_value = mock_storage
        sb = MagicMock()

        delete_employee_exit(EXIT_ID, COMPANY_ID, supabase_client=sb)

        mock_repo.delete.assert_called_once_with(EXIT_ID, COMPANY_ID)
        mock_update_emp.assert_called_once_with(EMPLOYEE_ID, "actif", None, sb)

    def test_raises_404_when_exit_not_found(
        self, mock_repo_class, mock_update_emp, mock_storage_provider, mock_get_paths
    ):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            delete_employee_exit(EXIT_ID, COMPANY_ID, supabase_client=MagicMock())
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.commands.ExitDocumentRepository")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestCreateExitDocument:
    """Commande create_exit_document."""

    def test_creates_document_when_exit_exists(
        self, mock_exit_repo_class, mock_doc_repo_class
    ):
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_by_id.return_value = _make_exit_record()
        mock_exit_repo_class.return_value = mock_exit_repo
        mock_doc_repo = MagicMock()
        doc_created = {"id": "doc-1", "exit_id": EXIT_ID, "filename": "letter.pdf"}
        mock_doc_repo.create.return_value = doc_created
        mock_doc_repo_class.return_value = mock_doc_repo

        result = create_exit_document(
            EXIT_ID,
            COMPANY_ID,
            {
                "document_type": "lettre_demission",
                "storage_path": "exits/exit-1/letter.pdf",
                "filename": "letter.pdf",
            },
            USER_ID,
            supabase_client=MagicMock(),
        )
        assert result["id"] == "doc-1"
        mock_doc_repo.create.assert_called_once()

    def test_raises_404_when_exit_not_found(
        self, mock_exit_repo_class, mock_doc_repo_class
    ):
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_by_id.return_value = None
        mock_exit_repo_class.return_value = mock_exit_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            create_exit_document(
                EXIT_ID,
                COMPANY_ID,
                {
                    "document_type": "lettre_demission",
                    "storage_path": "x",
                    "filename": "x",
                },
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.commands.get_exit_document_generator")
@patch("app.modules.employee_exits.application.commands.get_exit_storage_provider")
@patch("app.modules.employee_exits.application.commands.get_company_by_id")
@patch("app.modules.employee_exits.application.commands.ExitDocumentRepository")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestGenerateExitDocument:
    """Commande generate_exit_document."""

    def test_raises_400_for_unknown_document_type(
        self,
        mock_exit_repo_class,
        mock_doc_repo_class,
        mock_company,
        mock_storage,
        mock_generator,
    ):
        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            generate_exit_document(
                EXIT_ID,
                COMPANY_ID,
                "unknown_type",
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "non générable" in exc_info.value.detail

    def test_raises_404_when_exit_not_found(
        self,
        mock_exit_repo_class,
        mock_doc_repo_class,
        mock_company,
        mock_storage,
        mock_generator,
    ):
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_with_employee.return_value = None
        mock_exit_repo_class.return_value = mock_exit_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            generate_exit_document(
                EXIT_ID,
                COMPANY_ID,
                "certificat_travail",
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404

    def test_generates_certificat_travail(
        self,
        mock_exit_repo_class,
        mock_doc_repo_class,
        mock_company,
        mock_storage,
        mock_generator,
    ):
        exit_data = _make_exit_record()
        exit_data["employees"] = {"first_name": "Jean", "last_name": "Dupont"}
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_with_employee.return_value = exit_data
        mock_exit_repo_class.return_value = mock_exit_repo
        mock_company.return_value = {"name": "Test Co", "siret": "123"}
        gen = MagicMock()
        gen.generate_certificat_travail.return_value = b"pdf-content"
        mock_generator.return_value = gen
        mock_doc_repo = MagicMock()
        mock_doc_repo.create.return_value = {"id": "doc-gen-1", "filename": "cert.pdf"}
        mock_doc_repo_class.return_value = mock_doc_repo
        storage = MagicMock()
        mock_storage.return_value = storage

        result = generate_exit_document(
            EXIT_ID,
            COMPANY_ID,
            "certificat_travail",
            USER_ID,
            supabase_client=MagicMock(),
        )
        assert result["success"] is True
        assert result["document_type"] == "certificat_travail"
        gen.generate_certificat_travail.assert_called_once()
        mock_doc_repo.create.assert_called_once()


@patch("app.modules.employee_exits.application.commands.get_exit_storage_provider")
@patch("app.modules.employee_exits.application.commands.ExitDocumentRepository")
class TestDeleteExitDocument:
    """Commande delete_exit_document."""

    def test_deletes_document(self, mock_doc_repo_class, mock_storage_provider):
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = {
            "id": "doc-1",
            "storage_path": "exits/1/doc.pdf",
        }
        mock_doc_repo_class.return_value = mock_doc_repo
        storage = MagicMock()
        mock_storage_provider.return_value = storage

        delete_exit_document(EXIT_ID, "doc-1", COMPANY_ID, supabase_client=MagicMock())

        storage.remove.assert_called_once_with(["exits/1/doc.pdf"])
        mock_doc_repo.delete.assert_called_once_with("doc-1", EXIT_ID, COMPANY_ID)

    def test_raises_404_when_document_not_found(
        self, mock_doc_repo_class, mock_storage_provider
    ):
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = None
        mock_doc_repo_class.return_value = mock_doc_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            delete_exit_document(
                EXIT_ID, "doc-unknown", COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.commands.ExitChecklistRepository")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
class TestAddChecklistItem:
    """Commande add_checklist_item."""

    def test_adds_item_when_exit_exists(
        self, mock_exit_repo_class, mock_checklist_repo_class
    ):
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_by_id.return_value = _make_exit_record()
        mock_exit_repo_class.return_value = mock_exit_repo
        mock_checklist = MagicMock()
        item_created = {
            "id": "item-1",
            "item_code": "custom",
            "item_label": "Custom item",
        }
        mock_checklist.add_item.return_value = item_created
        mock_checklist_repo_class.return_value = mock_checklist

        result = add_checklist_item(
            EXIT_ID,
            COMPANY_ID,
            {
                "item_code": "custom",
                "item_label": "Custom item",
                "item_category": "autre",
            },
            supabase_client=MagicMock(),
        )
        assert result["id"] == "item-1"

    def test_raises_404_when_exit_not_found(
        self, mock_exit_repo_class, mock_checklist_repo_class
    ):
        mock_exit_repo = MagicMock()
        mock_exit_repo.get_by_id.return_value = None
        mock_exit_repo_class.return_value = mock_exit_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            add_checklist_item(
                EXIT_ID,
                COMPANY_ID,
                {"item_code": "x", "item_label": "x"},
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404


@patch("app.modules.employee_exits.application.commands.ExitChecklistRepository")
class TestMarkChecklistItemComplete:
    """Commande mark_checklist_item_complete."""

    def test_raises_404_when_item_not_found(self, mock_checklist_repo_class):
        mock_checklist = MagicMock()
        mock_checklist.get_item.return_value = None
        mock_checklist_repo_class.return_value = mock_checklist

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            mark_checklist_item_complete(
                EXIT_ID,
                "item-1",
                COMPANY_ID,
                {"is_completed": True},
                USER_ID,
                supabase_client=MagicMock(),
            )
        assert exc_info.value.status_code == 404

    def test_updates_completed_and_sets_completed_by(self, mock_checklist_repo_class):
        item = {"id": "item-1", "exit_id": EXIT_ID, "is_completed": False}
        updated = {**item, "is_completed": True, "completed_by": USER_ID}
        mock_checklist = MagicMock()
        mock_checklist.get_item.return_value = item
        mock_checklist.update_item.return_value = updated
        mock_checklist_repo_class.return_value = mock_checklist

        result = mark_checklist_item_complete(
            EXIT_ID,
            "item-1",
            COMPANY_ID,
            {"is_completed": True},
            USER_ID,
            supabase_client=MagicMock(),
        )
        assert result["is_completed"] is True
        call_args = mock_checklist.update_item.call_args[0]
        update_data = call_args[3]
        assert update_data.get("is_completed") is True
        assert update_data.get("completed_by") == USER_ID


@patch("app.modules.employee_exits.application.commands.ExitChecklistRepository")
class TestDeleteChecklistItem:
    """Commande delete_checklist_item."""

    def test_raises_404_when_item_not_found(self, mock_checklist_repo_class):
        mock_checklist = MagicMock()
        mock_checklist.get_item.return_value = None
        mock_checklist_repo_class.return_value = mock_checklist

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            delete_checklist_item(
                EXIT_ID, "item-1", COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404

    def test_raises_400_when_item_required(self, mock_checklist_repo_class):
        mock_checklist = MagicMock()
        mock_checklist.get_item.return_value = {"id": "item-1", "is_required": True}
        mock_checklist_repo_class.return_value = mock_checklist

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            delete_checklist_item(
                EXIT_ID, "item-1", COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 400
        assert "obligatoire" in exc_info.value.detail

    def test_deletes_optional_item(self, mock_checklist_repo_class):
        mock_checklist = MagicMock()
        mock_checklist.get_item.return_value = {"id": "item-1", "is_required": False}
        mock_checklist_repo_class.return_value = mock_checklist

        delete_checklist_item(
            EXIT_ID, "item-1", COMPANY_ID, supabase_client=MagicMock()
        )
        mock_checklist.delete_item.assert_called_once_with(
            "item-1", EXIT_ID, COMPANY_ID
        )


@patch("app.modules.employee_exits.application.commands.ExitDocumentRepository")
class TestUnpublishExitDocument:
    """Commande unpublish_exit_document."""

    def test_raises_404_when_document_not_found(self, mock_doc_repo_class):
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = None
        mock_doc_repo_class.return_value = mock_doc_repo

        with pytest.raises(EmployeeExitApplicationError) as exc_info:
            unpublish_exit_document(
                EXIT_ID, "doc-1", COMPANY_ID, supabase_client=MagicMock()
            )
        assert exc_info.value.status_code == 404

    def test_updates_published_to_employee_false(self, mock_doc_repo_class):
        doc = {"id": "doc-1", "published_to_employee": True}
        updated = {**doc, "published_to_employee": False}
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_id.return_value = doc
        mock_doc_repo.update.return_value = updated
        mock_doc_repo_class.return_value = mock_doc_repo

        result = unpublish_exit_document(
            EXIT_ID, "doc-1", COMPANY_ID, supabase_client=MagicMock()
        )
        assert result["published_to_employee"] is False
