"""
Tests unitaires du service applicatif expenses (application/service.py).

Le service orchestre les commands/queries ; on mocke les commandes et queries
pour vérifier la délégation et les paramètres passés.
"""
from datetime import date
from unittest.mock import MagicMock, patch

from app.modules.expenses.application.service import ExpenseApplicationService
from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    ListExpensesInput,
    UpdateExpenseStatusInput,
)


class TestExpenseApplicationServiceCreateExpense:
    """ExpenseApplicationService.create_expense."""

    def test_create_expense_delegates_to_command(self):
        input_ = CreateExpenseInput(
            employee_id="emp-001",
            date=date(2025, 3, 15),
            amount=100.0,
            type="Restaurant",
            description="Repas",
        )
        expected_result = {"id": "exp-new", "amount": 100.0, "status": "pending"}

        with patch(
            "app.modules.expenses.application.service.cmd_create_expense",
            return_value=expected_result,
        ) as mock_cmd:
            svc = ExpenseApplicationService()
            result = svc.create_expense(input_)

        mock_cmd.assert_called_once_with(input_)
        assert result == expected_result


class TestExpenseApplicationServiceUpdateExpenseStatus:
    """ExpenseApplicationService.update_expense_status."""

    def test_update_expense_status_delegates_to_command(self):
        input_ = UpdateExpenseStatusInput(expense_id="exp-123", status="validated")
        expected_result = {"id": "exp-123", "status": "validated"}

        with patch(
            "app.modules.expenses.application.service.cmd_update_expense_status",
            return_value=expected_result,
        ) as mock_cmd:
            svc = ExpenseApplicationService()
            result = svc.update_expense_status(input_)

        mock_cmd.assert_called_once_with(input_)
        assert result == expected_result

    def test_update_expense_status_returns_none_from_command(self):
        with patch(
            "app.modules.expenses.application.service.cmd_update_expense_status",
            return_value=None,
        ) as mock_cmd:
            svc = ExpenseApplicationService()
            result = svc.update_expense_status(
                UpdateExpenseStatusInput(expense_id="exp-404", status="rejected")
            )

        mock_cmd.assert_called_once()
        assert result is None


class TestExpenseApplicationServiceGetMyExpenses:
    """ExpenseApplicationService.get_my_expenses."""

    def test_get_my_expenses_delegates_to_query(self):
        expected_list = [
            {"id": "exp-1", "employee_id": "emp-001", "amount": 50.0},
        ]

        with patch(
            "app.modules.expenses.application.service.query_get_my_expenses",
            return_value=expected_list,
        ) as mock_query:
            svc = ExpenseApplicationService()
            result = svc.get_my_expenses("emp-001")

        mock_query.assert_called_once_with("emp-001")
        assert result == expected_list
        assert len(result) == 1

    def test_get_my_expenses_empty_list(self):
        with patch(
            "app.modules.expenses.application.service.query_get_my_expenses",
            return_value=[],
        ):
            svc = ExpenseApplicationService()
            result = svc.get_my_expenses("emp-empty")

        assert result == []


class TestExpenseApplicationServiceGetAllExpenses:
    """ExpenseApplicationService.get_all_expenses."""

    def test_get_all_expenses_delegates_with_status(self):
        input_ = ListExpensesInput(status="validated")
        expected_list = [{"id": "exp-1", "status": "validated"}]

        with patch(
            "app.modules.expenses.application.service.query_get_all_expenses",
            return_value=expected_list,
        ) as mock_query:
            svc = ExpenseApplicationService()
            result = svc.get_all_expenses(input_)

        mock_query.assert_called_once_with("validated")
        assert result == expected_list

    def test_get_all_expenses_delegates_without_status(self):
        input_ = ListExpensesInput(status=None)
        with patch(
            "app.modules.expenses.application.service.query_get_all_expenses",
            return_value=[],
        ) as mock_query:
            svc = ExpenseApplicationService()
            svc.get_all_expenses(input_)

        mock_query.assert_called_once_with(None)


class TestExpenseApplicationServiceGetSignedUploadUrl:
    """ExpenseApplicationService.get_signed_upload_url."""

    def test_get_signed_upload_url_delegates_to_query(self):
        expected = {"path": "emp-001/2025-file.pdf", "signedURL": "https://signed"}

        with patch(
            "app.modules.expenses.application.service.query_get_signed_upload_url",
            return_value=expected,
        ) as mock_query:
            svc = ExpenseApplicationService()
            result = svc.get_signed_upload_url("emp-001", "facture.pdf")

        mock_query.assert_called_once_with("emp-001", "facture.pdf")
        assert result == expected
        assert result["signedURL"] == "https://signed"
