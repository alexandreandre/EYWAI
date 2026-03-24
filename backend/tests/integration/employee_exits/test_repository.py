"""
Tests d'intégration des repositories du module employee_exits.

Vérifient le comportement des repositories contre un client Supabase mocké.
Pour des tests contre une DB de test réelle, fournir la fixture db_session dans conftest.py
(connexion à une base de test avec tables employee_exits, exit_documents, exit_checklist_items,
employees, companies) et utiliser un client Supabase initialisé avec cette session.
"""
from unittest.mock import MagicMock

import pytest

from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitChecklistRepository,
    ExitDocumentRepository,
)


pytestmark = pytest.mark.integration

COMPANY_ID = "company-repo-test"
EXIT_ID = "exit-repo-test"
EMPLOYEE_ID = "employee-repo-test"
DOC_ID = "doc-repo-test"
ITEM_ID = "item-repo-test"


class TestEmployeeExitRepository:
    """Repository employee_exits (table employee_exits)."""

    def test_create_calls_table_insert(self):
        """create() appelle table('employee_exits').insert().execute()."""
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_response = MagicMock()
        mock_response.data = [{"id": EXIT_ID, "company_id": COMPANY_ID, "employee_id": EMPLOYEE_ID}]
        mock_table.insert.return_value.execute.return_value = mock_response

        repo = EmployeeExitRepository(mock_sb)
        data = {
            "company_id": COMPANY_ID,
            "employee_id": EMPLOYEE_ID,
            "exit_type": "demission",
            "status": "demission_recue",
            "exit_request_date": "2025-01-15",
            "last_working_day": "2025-03-15",
            "notice_period_days": 60,
            "is_gross_misconduct": False,
        }
        result = repo.create(data)

        mock_sb.table.assert_called_with("employee_exits")
        mock_table.insert.assert_called_once_with(data)
        assert result["id"] == EXIT_ID
        assert result["company_id"] == COMPANY_ID

    def test_get_by_id_returns_exit_when_found(self):
        """get_by_id() appelle select et retourne la sortie si trouvée."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": EXIT_ID, "company_id": COMPANY_ID}

        repo = EmployeeExitRepository(mock_sb)
        result = repo.get_by_id(EXIT_ID, COMPANY_ID)

        mock_sb.table.assert_called_with("employee_exits")
        mock_sb.table.return_value.select.assert_called_once_with("*")
        assert result["id"] == EXIT_ID

    def test_list_returns_list_from_table(self):
        """list() interroge la table employee_exits et retourne une liste."""
        mock_sb = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select  # chaîne .eq().eq().order()
        mock_select.order.return_value.execute.return_value.data = []
        mock_sb.table.return_value.select.return_value = mock_select

        repo = EmployeeExitRepository(mock_sb)
        result = repo.list(COMPANY_ID, status="demission_effective", exit_type="demission", employee_id=EMPLOYEE_ID)

        mock_sb.table.assert_called_with("employee_exits")
        assert result == []

    def test_update_calls_table_update(self):
        """update() appelle table().update(data).eq(id).eq(company_id).execute()."""
        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": EXIT_ID, "status": "demission_effective"}]
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = mock_resp
        mock_sb.table.return_value.update.return_value = chain

        repo = EmployeeExitRepository(mock_sb)
        result = repo.update(EXIT_ID, COMPANY_ID, {"status": "demission_effective"})

        mock_sb.table.return_value.update.assert_called_once_with({"status": "demission_effective"})
        assert result["status"] == "demission_effective"

    def test_delete_calls_table_delete(self):
        """delete() appelle table().delete().eq(id).eq(company_id).execute()."""
        mock_sb = MagicMock()
        chain = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value = chain

        repo = EmployeeExitRepository(mock_sb)
        result = repo.delete(EXIT_ID, COMPANY_ID)

        mock_sb.table.assert_called_with("employee_exits")
        assert result is True


class TestExitDocumentRepository:
    """Repository exit_documents."""

    def test_create_calls_table_insert(self):
        """create() insère dans exit_documents."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": DOC_ID, "exit_id": EXIT_ID, "storage_path": "exits/1/doc.pdf"}
        ]

        repo = ExitDocumentRepository(mock_sb)
        data = {"exit_id": EXIT_ID, "company_id": COMPANY_ID, "document_type": "certificat_travail", "storage_path": "exits/1/doc.pdf", "filename": "doc.pdf"}
        result = repo.create(data)

        mock_sb.table.assert_called_with("exit_documents")
        assert result["id"] == DOC_ID

    def test_list_by_exit_calls_select_eq_exit_id(self):
        """list_by_exit() filtre par exit_id et company_id."""
        mock_sb = MagicMock()
        chain = MagicMock()
        chain.order.return_value.execute.return_value.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = chain

        repo = ExitDocumentRepository(mock_sb)
        result = repo.list_by_exit(EXIT_ID, COMPANY_ID)

        mock_sb.table.assert_called_with("exit_documents")
        assert result == []

    def test_get_by_id_returns_document(self):
        """get_by_id() retourne le document si trouvé."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": DOC_ID,
            "exit_id": EXIT_ID,
            "company_id": COMPANY_ID,
        }

        repo = ExitDocumentRepository(mock_sb)
        result = repo.get_by_id(DOC_ID, EXIT_ID, COMPANY_ID)

        assert result["id"] == DOC_ID

    def test_delete_calls_table_delete(self):
        """delete() supprime le document."""
        mock_sb = MagicMock()
        chain = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value = chain

        repo = ExitDocumentRepository(mock_sb)
        repo.delete(DOC_ID, EXIT_ID, COMPANY_ID)

        mock_sb.table.assert_called_with("exit_documents")


class TestExitChecklistRepository:
    """Repository exit_checklist_items."""

    def test_create_many_calls_table_insert(self):
        """create_many() insère la liste d'items."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "item-1", "item_code": "badge_return"},
            {"id": "item-2", "item_code": "equipment_return"},
        ]

        repo = ExitChecklistRepository(mock_sb)
        items = [
            {"exit_id": EXIT_ID, "company_id": COMPANY_ID, "item_code": "badge_return", "item_label": "Badge", "item_category": "materiel", "is_required": True, "display_order": 0},
            {"exit_id": EXIT_ID, "company_id": COMPANY_ID, "item_code": "equipment_return", "item_label": "Matériel", "item_category": "materiel", "is_required": True, "display_order": 1},
        ]
        result = repo.create_many(items)

        mock_sb.table.assert_called_with("exit_checklist_items")
        mock_sb.table.return_value.insert.assert_called_once_with(items)
        assert len(result) == 2

    def test_list_by_exit_orders_by_display_order(self):
        """list_by_exit() appelle order('display_order')."""
        mock_sb = MagicMock()
        chain = MagicMock()
        chain.order.return_value.execute.return_value.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = chain

        repo = ExitChecklistRepository(mock_sb)
        repo.list_by_exit(EXIT_ID, COMPANY_ID)

        chain.order.assert_called_with("display_order")

    def test_get_item_returns_item(self):
        """get_item() retourne l'item si trouvé."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": ITEM_ID,
            "exit_id": EXIT_ID,
            "company_id": COMPANY_ID,
            "item_code": "badge_return",
            "is_completed": False,
        }

        repo = ExitChecklistRepository(mock_sb)
        result = repo.get_item(ITEM_ID, EXIT_ID, COMPANY_ID)

        assert result["id"] == ITEM_ID
        assert result["item_code"] == "badge_return"

    def test_update_item_calls_table_update(self):
        """update_item() met à jour l'item."""
        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": ITEM_ID, "is_completed": True}]
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_resp
        mock_sb.table.return_value.update.return_value = chain

        repo = ExitChecklistRepository(mock_sb)
        result = repo.update_item(ITEM_ID, EXIT_ID, COMPANY_ID, {"is_completed": True})

        assert result["is_completed"] is True
