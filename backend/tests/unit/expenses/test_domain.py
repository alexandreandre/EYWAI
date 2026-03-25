"""
Tests unitaires du domaine expenses : entités, value objects, enums et règles.

Sans DB, sans HTTP. Couvre toutes les entités et règles du domain/.
"""

from datetime import date, datetime

import pytest

from app.modules.expenses.domain.entities import ExpenseReportEntity
from app.modules.expenses.domain.value_objects import ExpenseAmount
from app.modules.expenses.domain.enums import ExpenseStatus, ExpenseType
from app.modules.expenses.domain.rules import (
    get_initial_expense_status,
    validate_expense_status_transition,
    is_valid_status_for_update,
    INITIAL_EXPENSE_STATUS,
)


class TestExpenseStatus:
    """Enum ExpenseStatus."""

    def test_pending_value(self):
        assert ExpenseStatus.PENDING.value == "pending"

    def test_validated_value(self):
        assert ExpenseStatus.VALIDATED.value == "validated"

    def test_rejected_value(self):
        assert ExpenseStatus.REJECTED.value == "rejected"

    def test_from_string(self):
        assert ExpenseStatus("pending") == ExpenseStatus.PENDING
        assert ExpenseStatus("validated") == ExpenseStatus.VALIDATED
        assert ExpenseStatus("rejected") == ExpenseStatus.REJECTED


class TestExpenseType:
    """Enum ExpenseType."""

    def test_restaurant_value(self):
        assert ExpenseType.RESTAURANT.value == "Restaurant"

    def test_transport_value(self):
        assert ExpenseType.TRANSPORT.value == "Transport"

    def test_hotel_value(self):
        assert ExpenseType.HOTEL.value == "Hôtel"

    def test_fournitures_value(self):
        assert ExpenseType.FOURNITURES.value == "Fournitures"

    def test_autre_value(self):
        assert ExpenseType.AUTRE.value == "Autre"

    def test_from_string(self):
        assert ExpenseType("Restaurant") == ExpenseType.RESTAURANT
        assert ExpenseType("Transport") == ExpenseType.TRANSPORT
        assert ExpenseType("Hôtel") == ExpenseType.HOTEL


class TestExpenseReportEntity:
    """Entité domaine ExpenseReportEntity."""

    def test_entity_creation_with_required_fields(self):
        entity = ExpenseReportEntity(
            id="exp-001",
            employee_id="emp-001",
            date=date(2025, 3, 15),
            amount=42.50,
            type="Restaurant",
            status="pending",
        )
        assert entity.id == "exp-001"
        assert entity.employee_id == "emp-001"
        assert entity.date == date(2025, 3, 15)
        assert entity.amount == 42.50
        assert entity.type == "Restaurant"
        assert entity.status == "pending"
        assert entity.company_id is None
        assert entity.description is None
        assert entity.receipt_url is None
        assert entity.filename is None
        assert entity.created_at is None

    def test_entity_with_all_fields(self):
        created = datetime(2025, 3, 15, 10, 30, 0)
        entity = ExpenseReportEntity(
            id="exp-002",
            employee_id="emp-002",
            date=date(2025, 3, 10),
            amount=120.0,
            type="Transport",
            status="validated",
            company_id="co-001",
            description="Train Paris-Lyon",
            receipt_url="emp-002/2025-03-10-receipt.pdf",
            filename="receipt.pdf",
            created_at=created,
        )
        assert entity.company_id == "co-001"
        assert entity.description == "Train Paris-Lyon"
        assert entity.receipt_url == "emp-002/2025-03-10-receipt.pdf"
        assert entity.filename == "receipt.pdf"
        assert entity.created_at == created


class TestExpenseAmount:
    """Value object ExpenseAmount."""

    def test_amount_default_currency_eur(self):
        vo = ExpenseAmount(value=99.99)
        assert vo.value == 99.99
        assert vo.currency == "EUR"

    def test_amount_with_custom_currency(self):
        vo = ExpenseAmount(value=50.0, currency="USD")
        assert vo.value == 50.0
        assert vo.currency == "USD"

    def test_frozen_immutable(self):
        vo = ExpenseAmount(value=10.0)
        with pytest.raises(Exception):
            vo.value = 20.0


class TestGetInitialExpenseStatus:
    """Règle get_initial_expense_status."""

    def test_returns_pending(self):
        assert get_initial_expense_status() == "pending"
        assert get_initial_expense_status() == INITIAL_EXPENSE_STATUS


class TestValidateExpenseStatusTransition:
    """Règle validate_expense_status_transition."""

    def test_pending_to_validated_allowed(self):
        err = validate_expense_status_transition("pending", "validated")
        assert err is None

    def test_pending_to_rejected_allowed(self):
        err = validate_expense_status_transition("pending", "rejected")
        assert err is None

    def test_same_status_no_change_allowed(self):
        err = validate_expense_status_transition("pending", "pending")
        assert err is None
        err = validate_expense_status_transition("validated", "validated")
        assert err is None

    def test_validated_to_pending_forbidden(self):
        err = validate_expense_status_transition("validated", "pending")
        assert err is not None
        assert "Transition de statut non autorisée" in err
        assert "validated" in err
        assert "pending" in err
        assert "pending -> validated" in err

    def test_rejected_to_validated_forbidden(self):
        err = validate_expense_status_transition("rejected", "validated")
        assert err is not None
        assert "non autorisée" in err

    def test_pending_to_unknown_forbidden(self):
        err = validate_expense_status_transition("pending", "archived")
        assert err is not None
        assert "pending -> validated" in err or "pending -> rejected" in err


class TestIsValidStatusForUpdate:
    """Règle is_valid_status_for_update."""

    def test_validated_is_valid(self):
        assert is_valid_status_for_update("validated") is True

    def test_rejected_is_valid(self):
        assert is_valid_status_for_update("rejected") is True

    def test_pending_is_invalid(self):
        assert is_valid_status_for_update("pending") is False

    def test_unknown_status_is_invalid(self):
        assert is_valid_status_for_update("archived") is False
        assert is_valid_status_for_update("") is False
