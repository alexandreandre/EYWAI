"""
Tests d'intégration des repositories du module saisies_avances.

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir db_session (conftest) et données dans salary_seizures,
salary_advances, salary_advance_payments, employees pour des tests CRUD réels.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.modules.saisies_avances.infrastructure.repository import (
    AdvancePaymentRepository,
    AdvanceRepository,
    EmployeeCompanyProvider,
    SeizureRepository,
)


pytestmark = pytest.mark.integration


class TestSeizureRepository:
    """SeizureRepository (table salary_seizures)."""

    def test_create_calls_insert_and_returns_row(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            inserted = {"id": "s1", "employee_id": "emp1", "status": "active"}
            table.insert.return_value.execute.return_value = MagicMock(data=[inserted])
            supabase.table.return_value = table

            repo = SeizureRepository()
            data = {"employee_id": "emp1", "company_id": "co1", "type": "pension_alimentaire", "creditor_name": "X", "start_date": "2025-01-01", "status": "active"}
            result = repo.create(data)

            table.insert.assert_called_once_with(data)
            assert result == inserted

    def test_get_by_id_returns_row(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"id": "s1", "creditor_name": "Créancier"}
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SeizureRepository()
            result = repo.get_by_id("s1")

            assert result["id"] == "s1"
            assert result["creditor_name"] == "Créancier"
            chain.eq.assert_called_once_with("id", "s1")

    def test_get_by_id_returns_none_when_empty(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SeizureRepository()
            result = repo.get_by_id("s-inexistant")

            assert result is None

    def test_list_filters_by_employee_and_status(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            # list_ fait: select -> eq(employee_id) -> eq(status) -> order -> execute
            chain.eq.return_value = chain
            chain.order.return_value.execute.return_value = MagicMock(data=[{"id": "s1"}])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SeizureRepository()
            result = repo.list_(employee_id="emp1", status="active")

            assert len(result) == 1
            chain.eq.assert_any_call("employee_id", "emp1")
            chain.eq.assert_any_call("status", "active")

    def test_update_returns_updated_row(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[{"id": "s1", "status": "suspended"}])
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = SeizureRepository()
            result = repo.update("s1", {"status": "suspended"})

            assert result["status"] == "suspended"
            table.update.assert_called_once_with({"status": "suspended"})
            chain.eq.assert_called_once_with("id", "s1")

    def test_delete_calls_delete_eq(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.delete.return_value = chain
            chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = SeizureRepository()
            repo.delete("s1")

            chain.eq.assert_called_once_with("id", "s1")


class TestAdvanceRepository:
    """AdvanceRepository (table salary_advances)."""

    def test_create_returns_inserted_row(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            inserted = {"id": "a1", "employee_id": "emp1", "status": "pending"}
            table.insert.return_value.execute.return_value = MagicMock(data=[inserted])
            supabase.table.return_value = table

            repo = AdvanceRepository()
            data = {"employee_id": "emp1", "company_id": "co1", "requested_amount": 200, "requested_date": "2025-03-01", "status": "pending", "repayment_mode": "single", "repayment_months": 1, "remaining_amount": 0}
            result = repo.create(data)

            assert result == inserted

    def test_get_by_id_returns_none_when_empty(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = AdvanceRepository()
            result = repo.get_by_id("a-inexistant")
            assert result is None

    def test_list_returns_empty_list(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.order.return_value.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = AdvanceRepository()
            result = repo.list_()
            assert result == []


class TestAdvancePaymentRepository:
    """AdvancePaymentRepository (table salary_advance_payments)."""

    def test_list_by_advance_id_returns_payments(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[{"id": "pay1", "payment_amount": 100}]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = AdvancePaymentRepository()
            result = repo.list_by_advance_id("a1")

            assert len(result) == 1
            assert result[0]["payment_amount"] == 100

    def test_get_total_paid_by_advance_id_sums_amounts(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"payment_amount": 100}, {"payment_amount": 50}]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = AdvancePaymentRepository()
            result = repo.get_total_paid_by_advance_id("a1")

            assert result == Decimal("150")

    def test_delete_calls_delete_eq(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.delete.return_value = chain
            chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = AdvancePaymentRepository()
            repo.delete("pay1")
            chain.eq.assert_called_once_with("id", "pay1")


class TestEmployeeCompanyProvider:
    """EmployeeCompanyProvider (lecture company_id depuis employees)."""

    def test_get_company_id_returns_id(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data={"company_id": "co-123"}
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            provider = EmployeeCompanyProvider()
            result = provider.get_company_id("emp1")

            assert result == "co-123"
            chain.eq.assert_called_once_with("id", "emp1")

    def test_get_company_id_returns_none_when_no_row(self):
        with patch("app.modules.saisies_avances.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
            table.select.return_value = chain
            supabase.table.return_value = table

            provider = EmployeeCompanyProvider()
            result = provider.get_company_id("emp-inexistant")
            assert result is None
