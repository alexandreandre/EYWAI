"""
Tests d'intégration du repository payslips (PayslipRepository).

Vérifie que le repository délègue correctement à Supabase (table payslips, storage).
Les appels DB/Storage sont mockés (pas de DB réelle). Pour des tests contre une DB de test,
prévoir db_session et données dans payslips (fixture à documenter dans conftest.py).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.infrastructure.repository import PayslipRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    """Instance du repository à tester."""
    return PayslipRepository()


class TestPayslipRepositoryGetById:
    """get_by_id."""

    def test_returns_row_when_found(self, repo: PayslipRepository):
        """Retourne la ligne quand le bulletin existe."""
        row = {
            "id": "ps-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "month": 3,
            "year": 2024,
            "payslip_data": {"net_a_payer": 2500},
        }
        mock_chain = MagicMock()
        mock_chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=row
        )

        with patch(
            "app.modules.payslips.infrastructure.repository.supabase"
        ) as mock_sb:
            mock_sb.table.return_value.select.return_value = mock_chain
            result = repo.get_by_id("ps-1")

        mock_sb.table.assert_called_once_with("payslips")
        mock_chain.eq.assert_called_once_with("id", "ps-1")
        assert result == row

    def test_returns_none_when_not_found(self, repo: PayslipRepository):
        """Retourne None quand le bulletin n'existe pas."""
        mock_chain = MagicMock()
        mock_chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=None
        )

        with patch(
            "app.modules.payslips.infrastructure.repository.supabase"
        ) as mock_sb:
            mock_sb.table.return_value.select.return_value = mock_chain
            result = repo.get_by_id("ps-unknown")

        assert result is None


class TestPayslipRepositoryListByEmployee:
    """list_by_employee."""

    def test_returns_list_ordered_by_year_month_desc(self, repo: PayslipRepository):
        """Retourne la liste des bulletins de l'employé, triée year desc, month desc."""
        data = [
            {"id": "ps-2", "employee_id": "emp-1", "year": 2024, "month": 6},
            {"id": "ps-1", "employee_id": "emp-1", "year": 2024, "month": 3},
        ]
        mock_chain = MagicMock()
        mock_chain.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=data
        )

        with patch(
            "app.modules.payslips.infrastructure.repository.supabase"
        ) as mock_sb:
            mock_sb.table.return_value.select.return_value = mock_chain
            result = repo.list_by_employee("emp-1")

        mock_sb.table.assert_called_once_with("payslips")
        mock_chain.eq.assert_called_once_with("employee_id", "emp-1")
        assert result == data

    def test_returns_empty_list_when_no_payslips(self, repo: PayslipRepository):
        """Retourne [] quand l'employé n'a pas de bulletins."""
        mock_chain = MagicMock()
        mock_chain.eq.return_value.order.return_value.order.return_value.execute.return_value = MagicMock(
            data=None
        )

        with patch(
            "app.modules.payslips.infrastructure.repository.supabase"
        ) as mock_sb:
            mock_sb.table.return_value.select.return_value = mock_chain
            result = repo.list_by_employee("emp-unknown")

        assert result == []


class TestPayslipRepositoryDelete:
    """delete : BDD + storage + recalc COR."""

    def test_delete_fetches_row_then_deletes_table_and_storage(
        self, repo: PayslipRepository
    ):
        """delete récupère la ligne, supprime en BDD, appelle recalc COR et supprime le fichier storage."""
        row = {
            "pdf_storage_path": "co/emp/bulletins/Bulletin_03-2024.pdf",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "month": 3,
        }
        select_chain = MagicMock()
        select_chain.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=row)
        )

        delete_chain = MagicMock()
        storage_mock = MagicMock()
        table_return = MagicMock()
        table_return.select.return_value = select_chain
        table_return.delete.return_value = delete_chain

        with (
            patch("app.modules.payslips.infrastructure.repository.supabase") as mock_sb,
            patch(
                "app.modules.payslips.infrastructure.repository.recalculer_credits_repos_employe"
            ) as mock_recalc,
        ):
            mock_sb.table.return_value = table_return
            mock_sb.storage.from_.return_value = storage_mock

            repo.delete("ps-1")

        # Vérification select (colonnes spécifiques)
        table_return.select.assert_any_call(
            "pdf_storage_path, employee_id, company_id, year, month"
        )
        select_chain.eq.assert_called_with("id", "ps-1")
        # Vérification delete table
        delete_chain.eq.assert_called_once_with("id", "ps-1")
        delete_chain.eq.return_value.execute.assert_called_once()
        # Recalc COR
        mock_recalc.assert_called_once_with("emp-1", "co-1", 2024)
        # Storage remove
        storage_mock.remove.assert_called_once_with([row["pdf_storage_path"]])

    def test_delete_skips_recalc_and_storage_when_no_row(self, repo: PayslipRepository):
        """Si la ligne n'existe pas (data vide), pas d'appel recalc ni storage."""
        select_chain = MagicMock()
        select_chain.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=None)
        )
        table_return = MagicMock()
        table_return.select.return_value = select_chain
        table_return.delete.return_value = MagicMock()

        with (
            patch("app.modules.payslips.infrastructure.repository.supabase") as mock_sb,
            patch(
                "app.modules.payslips.infrastructure.repository.recalculer_credits_repos_employe"
            ) as mock_recalc,
        ):
            mock_sb.table.return_value = table_return

            repo.delete("ps-unknown")

        mock_recalc.assert_not_called()
        mock_sb.storage.from_.assert_not_called()

    def test_delete_skips_storage_when_no_pdf_path(self, repo: PayslipRepository):
        """Si pdf_storage_path est absent, ne pas appeler storage.remove."""
        row = {
            "pdf_storage_path": None,
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "month": 3,
        }
        select_chain = MagicMock()
        select_chain.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=row)
        )
        table_return = MagicMock()
        table_return.select.return_value = select_chain
        table_return.delete.return_value = MagicMock()

        with (
            patch("app.modules.payslips.infrastructure.repository.supabase") as mock_sb,
            patch(
                "app.modules.payslips.infrastructure.repository.recalculer_credits_repos_employe"
            ),
        ):
            mock_sb.table.return_value = table_return
            storage_from = mock_sb.storage.from_.return_value

            repo.delete("ps-1")

        storage_from.remove.assert_not_called()
