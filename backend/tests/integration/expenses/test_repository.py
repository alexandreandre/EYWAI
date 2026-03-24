"""
Tests d'intégration du repository expenses (ExpenseRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans expense_reports pour des tests CRUD réels.
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.modules.expenses.infrastructure.repository import ExpenseRepository
from app.modules.expenses.infrastructure.queries import (
    TABLE_EXPENSE_REPORTS,
    ORDER_BY_DATE_DESC,
    ORDER_BY_CREATED_AT_DESC,
    SELECT_ALL_WITH_EMPLOYEE,
)


pytestmark = pytest.mark.integration

EXPENSE_ID_1 = "exp-550e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID_1 = "emp-660e8400-e29b-41d4-a716-446655440002"


def _row(expense_id: str = EXPENSE_ID_1, employee_id: str = EMPLOYEE_ID_1, **kwargs):
    base = {
        "id": expense_id,
        "employee_id": employee_id,
        "date": "2025-03-15",
        "amount": 45.0,
        "type": "Restaurant",
        "status": "pending",
        "description": None,
        "receipt_url": None,
        "filename": None,
        "company_id": None,
        "created_at": datetime.now().isoformat(),
    }
    base.update(kwargs)
    return base


class TestExpenseRepositoryCreate:
    """create."""

    def test_create_calls_insert_with_data(self):
        data = {
            "employee_id": EMPLOYEE_ID_1,
            "date": "2025-03-15",
            "amount": 55.0,
            "type": "Transport",
            "status": "pending",
            "description": "Train",
            "receipt_url": None,
            "filename": None,
        }
        inserted = {**data, "id": "exp-new-123"}

        mock_client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[inserted])
        mock_client.table.return_value.insert.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.create(data)

        mock_client.table.assert_called_once_with(TABLE_EXPENSE_REPORTS)
        mock_client.table.return_value.insert.assert_called_once_with(data)
        assert result == inserted
        assert result["id"] == "exp-new-123"
        assert result["amount"] == 55.0

    def test_create_empty_response_raises(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.insert.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        with pytest.raises(ValueError) as exc_info:
            repo.create({"employee_id": "e1", "date": "2025-01-01", "amount": 10.0})
        assert "Échec" in str(exc_info.value)


class TestExpenseRepositoryGetById:
    """get_by_id."""

    def test_get_by_id_returns_row(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=[_row(EXPENSE_ID_1, status="validated")]
        )
        mock_client.table.return_value.select.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.get_by_id(EXPENSE_ID_1)

        mock_client.table.assert_called_once_with(TABLE_EXPENSE_REPORTS)
        mock_client.table.return_value.select.assert_called_once_with("*")
        mock_client.table.return_value.select.return_value.eq.assert_called_once_with(
            "id", EXPENSE_ID_1
        )
        assert result is not None
        assert result["id"] == EXPENSE_ID_1
        assert result["status"] == "validated"

    def test_get_by_id_no_data_returns_none(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.select.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.get_by_id("exp-inexistant")

        assert result is None


class TestExpenseRepositoryUpdateStatus:
    """update_status."""

    def test_update_status_calls_update_eq_execute(self):
        mock_client = MagicMock()
        chain = MagicMock()
        updated_row = _row(EXPENSE_ID_1, status="validated")
        chain.execute.return_value = MagicMock(data=[updated_row])
        mock_client.table.return_value.update.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.update_status(EXPENSE_ID_1, "validated")

        mock_client.table.return_value.update.assert_called_once_with(
            {"status": "validated"}
        )
        mock_client.table.return_value.update.return_value.eq.assert_called_once_with(
            "id", EXPENSE_ID_1
        )
        assert result is not None
        assert result["status"] == "validated"

    def test_update_status_no_data_returns_none(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.update.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.update_status("exp-404", "rejected")

        assert result is None


class TestExpenseRepositoryListByEmployeeId:
    """list_by_employee_id."""

    def test_list_by_employee_id_orders_by_date_desc(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.order.return_value.execute.return_value = MagicMock(
            data=[
                _row("exp-1", date="2025-03-20"),
                _row("exp-2", date="2025-03-15"),
            ]
        )
        mock_client.table.return_value.select.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.list_by_employee_id(EMPLOYEE_ID_1)

        mock_client.table.return_value.select.return_value.eq.assert_called_once_with(
            "employee_id", EMPLOYEE_ID_1
        )
        chain.order.assert_called_once_with(ORDER_BY_DATE_DESC, desc=True)
        assert len(result) == 2
        assert result[0]["date"] == "2025-03-20"

    def test_list_by_employee_id_empty_returns_empty_list(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.order.return_value.execute.return_value = MagicMock(data=None)
        mock_client.table.return_value.select.return_value.eq.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.list_by_employee_id("emp-empty")

        assert result == []


class TestExpenseRepositoryListAll:
    """list_all."""

    def test_list_all_selects_with_employee_join(self):
        mock_client = MagicMock()
        chain = MagicMock()
        chain.order.return_value.execute.return_value = MagicMock(
            data=[
                {**_row("exp-1"), "employee": {"id": "emp-1", "first_name": "Jean"}},
            ]
        )
        mock_client.table.return_value.select.return_value = chain

        repo = ExpenseRepository(supabase_client=mock_client)
        result = repo.list_all()

        mock_client.table.assert_called_once_with(TABLE_EXPENSE_REPORTS)
        mock_client.table.return_value.select.assert_called_once_with(
            SELECT_ALL_WITH_EMPLOYEE
        )
        chain.order.assert_called_once_with(ORDER_BY_CREATED_AT_DESC, desc=True)
        assert len(result) == 1
        assert result[0].get("employee", {}).get("first_name") == "Jean"

    def test_list_all_with_status_filters_by_status(self):
        mock_client = MagicMock()
        select_ret = MagicMock()
        eq_ret = MagicMock()
        eq_ret.order.return_value.execute.return_value = MagicMock(data=[])
        select_ret.eq.return_value = eq_ret
        mock_client.table.return_value.select.return_value = select_ret

        repo = ExpenseRepository(supabase_client=mock_client)
        repo.list_all(status="validated")

        select_ret.eq.assert_called_once_with("status", "validated")
