"""
Tests unitaires des commandes expenses (application/commands.py).

Chaque commande est testée avec le repository mocké (patch ExpenseRepository).
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.expenses.application.commands import (
    create_expense,
    update_expense_status,
)
from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseStatusInput,
)


class TestCreateExpense:
    """Commande create_expense."""

    def test_create_expense_calls_repo_create_with_payload(self):
        input_ = CreateExpenseInput(
            employee_id="emp-001",
            date=date(2025, 3, 15),
            amount=55.00,
            type="Restaurant",
            description="Déjeuner client",
            receipt_url="emp-001/2025-03-15-ticket.pdf",
            filename="ticket.pdf",
        )
        created_row = {
            "id": "exp-new-1",
            "employee_id": "emp-001",
            "date": "2025-03-15",
            "amount": 55.0,
            "type": "Restaurant",
            "status": "pending",
            "description": "Déjeuner client",
            "receipt_url": "emp-001/2025-03-15-ticket.pdf",
            "filename": "ticket.pdf",
        }
        mock_repo = MagicMock()
        mock_repo.create.return_value = created_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = create_expense(input_)

        mock_repo.create.assert_called_once()
        call_payload = mock_repo.create.call_args[0][0]
        assert call_payload["employee_id"] == "emp-001"
        assert call_payload["date"] == "2025-03-15"
        assert call_payload["amount"] == 55.0
        assert call_payload["type"] == "Restaurant"
        assert call_payload["status"] == "pending"
        assert call_payload["description"] == "Déjeuner client"
        assert call_payload["receipt_url"] == "emp-001/2025-03-15-ticket.pdf"
        assert call_payload["filename"] == "ticket.pdf"
        assert result == created_row
        assert result["id"] == "exp-new-1"

    def test_create_expense_without_optional_fields(self):
        input_ = CreateExpenseInput(
            employee_id="emp-002",
            date=date(2025, 3, 10),
            amount=30.0,
            type="Transport",
        )
        created_row = {
            "id": "exp-new-2",
            "employee_id": "emp-002",
            "date": "2025-03-10",
            "amount": 30.0,
            "type": "Transport",
            "status": "pending",
            "description": None,
            "receipt_url": None,
            "filename": None,
        }
        mock_repo = MagicMock()
        mock_repo.create.return_value = created_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = create_expense(input_)

        call_payload = mock_repo.create.call_args[0][0]
        assert call_payload["description"] is None
        assert call_payload["receipt_url"] is None
        assert call_payload["filename"] is None
        assert result["status"] == "pending"

    def test_create_expense_repo_raises_propagates(self):
        input_ = CreateExpenseInput(
            employee_id="emp-003",
            date=date(2025, 3, 1),
            amount=10.0,
            type="Fournitures",
        )
        mock_repo = MagicMock()
        mock_repo.create.side_effect = ValueError(
            "Échec de la création de la note de frais."
        )

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(ValueError) as exc_info:
                create_expense(input_)
        assert "Échec" in str(exc_info.value)


class TestUpdateExpenseStatus:
    """Commande update_expense_status."""

    def test_update_expense_status_calls_repo_update_status(self):
        input_ = UpdateExpenseStatusInput(
            expense_id="exp-123",
            status="validated",
        )
        updated_row = {
            "id": "exp-123",
            "employee_id": "emp-001",
            "date": "2025-03-15",
            "amount": 50.0,
            "type": "Restaurant",
            "status": "validated",
        }
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = updated_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        mock_repo.update_status.assert_called_once_with("exp-123", "validated")
        assert result == updated_row
        assert result["status"] == "validated"

    def test_update_expense_status_rejected(self):
        input_ = UpdateExpenseStatusInput(expense_id="exp-456", status="rejected")
        updated_row = {"id": "exp-456", "status": "rejected"}
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = updated_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        mock_repo.update_status.assert_called_once_with("exp-456", "rejected")
        assert result["status"] == "rejected"

    def test_update_expense_status_not_found_returns_none(self):
        input_ = UpdateExpenseStatusInput(
            expense_id="exp-inexistant", status="validated"
        )
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = None

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        assert result is None
        mock_repo.update_status.assert_called_once_with("exp-inexistant", "validated")
