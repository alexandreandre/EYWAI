"""
Tests d'intégration du repository employees : EmployeeRepository et ProfileRepository.

Vérifie les opérations CRUD contre une DB de test (ou Supabase mocké).
Avec db_session : tests réels contre les tables employees et profiles.
Sans DB de test : mocks Supabase pour valider la logique et les appels.

Fixture à prévoir dans conftest.py si besoin :
  - db_session : session ou client DB de test pour tests contre une vraie base.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.infrastructure.repository import (
    EmployeeRepository,
    ProfileRepository,
)


pytestmark = pytest.mark.integration


@patch("app.modules.employees.infrastructure.repository.supabase")
class TestEmployeeRepository:
    """EmployeeRepository : get_by_company, get_by_id, get_by_id_only, create, update, delete."""

    def test_get_by_company_calls_table_with_company_id_and_orders_by_last_name(
        self, mock_supabase
    ):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "e1", "last_name": "Dupont", "company_id": "c1"},
                {"id": "e2", "last_name": "Martin", "company_id": "c1"},
            ]
        )
        mock_table.select.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.get_by_company("c1")

        mock_table.select.assert_called_once_with("*")
        chain.eq.assert_called_once_with("company_id", "c1")
        chain.eq.return_value.order.assert_called_once_with("last_name")
        assert len(result) == 2
        assert result[0]["id"] == "e1"
        assert result[1]["last_name"] == "Martin"

    def test_get_by_company_empty_returns_empty_list(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.get_by_company("c1")
        assert result == []

    def test_get_by_id_returns_single_employee_when_found(self, mock_supabase):
        row = {"id": "e1", "first_name": "Jean", "company_id": "c1"}
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=row)
        )
        mock_table.select.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.get_by_id("e1", "c1")
        assert result == row
        chain.eq.assert_any_call("id", "e1")
        chain.eq.return_value.eq.assert_called_with("company_id", "c1")

    def test_get_by_id_returns_none_when_no_data(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=None)
        )
        mock_table.select.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.get_by_id("unknown", "c1")
        assert result is None

    def test_get_by_id_only_filters_by_id_only(self, mock_supabase):
        row = {"id": "e1", "company_id": "c1", "first_name": "Jean"}
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=row
        )
        mock_table.select.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.get_by_id_only("e1")
        assert result == row
        chain.eq.assert_called_once_with("id", "e1")

    def test_create_calls_insert_and_returns_first_row(self, mock_supabase):
        insert_data = {"id": "e1", "first_name": "Jean", "company_id": "c1"}
        mock_table = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[insert_data])
        mock_table.insert.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.create(insert_data)
        mock_table.insert.assert_called_once_with(insert_data)
        assert result == insert_data

    def test_create_raises_when_no_data_returned(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=None)
        mock_table.insert.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        with pytest.raises(RuntimeError):
            repo.create({"id": "e1", "company_id": "c1"})

    def test_update_returns_updated_row(self, mock_supabase):
        updated = {"id": "e1", "first_name": "Paul", "company_id": "c1"}
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=[updated])
        mock_table.update.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.update("e1", {"first_name": "Paul"})
        mock_table.update.assert_called_once_with({"first_name": "Paul"})
        chain.eq.assert_called_once_with("id", "e1")
        assert result == updated

    def test_update_returns_none_when_no_data(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=None)
        mock_table.update.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.update("unknown", {"first_name": "X"})
        assert result is None

    def test_delete_calls_delete_eq_then_execute(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = None
        mock_table.delete.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = EmployeeRepository()
        result = repo.delete("e1")
        mock_table.delete.assert_called_once()
        chain.eq.assert_called_once_with("id", "e1")
        assert result is True


@patch("app.modules.employees.infrastructure.repository.supabase")
class TestProfileRepository:
    """ProfileRepository : upsert."""

    def test_upsert_calls_table_upsert_with_profile_data(self, mock_supabase):
        profile_data = {
            "id": "user-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "role": "collaborateur",
            "company_id": "c1",
        }
        mock_table = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[profile_data])
        mock_table.upsert.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = ProfileRepository()
        result = repo.upsert(profile_data)
        mock_table.upsert.assert_called_once_with(profile_data)
        assert result == profile_data

    def test_upsert_raises_when_no_data_returned(self, mock_supabase):
        mock_table = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=None)
        mock_table.upsert.return_value = chain
        mock_supabase.table.return_value = mock_table

        repo = ProfileRepository()
        with pytest.raises(RuntimeError):
            repo.upsert({"id": "u1", "company_id": "c1"})
