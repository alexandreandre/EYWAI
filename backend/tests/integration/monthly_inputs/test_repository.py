"""
Tests d'intégration du repository monthly_inputs (SupabaseMonthlyInputsRepository).

Sans DB réelle : mock de Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans la table monthly_inputs pour des tests CRUD réels.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.monthly_inputs.infrastructure.repository import (
    SupabaseMonthlyInputsRepository,
)


pytestmark = pytest.mark.integration


def _row(**kwargs):
    base = {
        "id": "mi-1",
        "employee_id": "550e8400-e29b-41d4-a716-446655440000",
        "year": 2025,
        "month": 3,
        "name": "Prime",
        "amount": 100.0,
        "description": None,
        "is_socially_taxed": True,
        "is_taxable": True,
        "created_at": "2025-03-01T10:00:00",
        "updated_at": None,
    }
    base.update(kwargs)
    return base


class TestSupabaseMonthlyInputsRepositoryListByPeriod:
    """list_by_period."""

    def test_list_by_period_calls_match_order_execute(self):
        """Select * sur monthly_inputs avec match year/month et order created_at desc."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.match.return_value.order.return_value.execute.return_value = MagicMock(
                data=[_row(), _row(id="mi-2", name="Acompte", amount=50.0)]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.list_by_period(2025, 3)

            table.select.assert_called_once_with("*")
            chain.match.assert_called_once_with({"year": 2025, "month": 3})
            chain.match.return_value.order.assert_called_once_with(
                "created_at", desc=True
            )
            assert len(result) == 2
            assert result[0]["name"] == "Prime"
            assert result[1]["name"] == "Acompte"

    def test_list_by_period_empty_returns_empty_list(self):
        """Aucune ligne → data vide → liste vide."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.match.return_value.order.return_value.execute.return_value = MagicMock(
                data=[]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.list_by_period(2024, 12)

            assert result == []


class TestSupabaseMonthlyInputsRepositoryListByEmployeePeriod:
    """list_by_employee_period."""

    def test_list_by_employee_period_calls_match_with_employee_id(self):
        """Match employee_id, year, month ; order created_at desc."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.match.return_value.order.return_value.execute.return_value = MagicMock(
                data=[_row(employee_id="emp-1")]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.list_by_employee_period("emp-1", 2025, 6)

            chain.match.assert_called_once_with(
                {"employee_id": "emp-1", "year": 2025, "month": 6}
            )
            assert len(result) == 1
            assert result[0]["employee_id"] == "emp-1"


class TestSupabaseMonthlyInputsRepositoryInsertBatch:
    """insert_batch."""

    def test_insert_batch_calls_insert_execute(self):
        """insert(rows).execute() → retourne response.data."""
        rows = [
            {"employee_id": "emp-1", "year": 2025, "month": 3, "name": "P1", "amount": 10.0},
            {"employee_id": "emp-1", "year": 2025, "month": 3, "name": "P2", "amount": 20.0},
        ]
        inserted = [_row(id="new-1", name="P1"), _row(id="new-2", name="P2")]

        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(data=inserted)
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.insert_batch(rows)

            table.insert.assert_called_once_with(rows)
            assert len(result) == 2
            assert result[0]["name"] == "P1"
            assert result[1]["name"] == "P2"

    def test_insert_batch_empty_data_returns_empty_list(self):
        """execute() sans data (None) → retourne []."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(data=None)
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.insert_batch([])

            assert result == []


class TestSupabaseMonthlyInputsRepositoryInsertOne:
    """insert_one."""

    def test_insert_one_returns_first_row(self):
        """insert(row).execute() → data[0]."""
        row = {"employee_id": "emp-1", "year": 2025, "month": 4, "name": "Prime", "amount": 100.0}
        inserted = _row(id="new-one", **row)

        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(
                data=[inserted]
            )
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.insert_one(row)

            table.insert.assert_called_once_with(row)
            assert result == inserted
            assert result["id"] == "new-one"

    def test_insert_one_empty_data_returns_empty_dict(self):
        """Pas de data → retourne {}."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(data=[])
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            result = repo.insert_one({"employee_id": "e", "year": 2025, "month": 1, "name": "X", "amount": 0})

            assert result == {}


class TestSupabaseMonthlyInputsRepositoryDeleteById:
    """delete_by_id."""

    def test_delete_by_id_calls_delete_eq_execute(self):
        """delete().eq("id", input_id).execute()."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.delete.return_value = chain
            chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            repo.delete_by_id("input-id-123")

            table.delete.assert_called_once()
            chain.eq.assert_called_once_with("id", "input-id-123")


class TestSupabaseMonthlyInputsRepositoryDeleteByIdAndEmployee:
    """delete_by_id_and_employee."""

    def test_delete_by_id_and_employee_calls_delete_eq_eq_execute(self):
        """delete().eq("id", ...).eq("employee_id", ...).execute()."""
        with patch(
            "app.modules.monthly_inputs.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.delete.return_value = chain
            chain.eq.return_value.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = SupabaseMonthlyInputsRepository()
            repo.delete_by_id_and_employee("input-1", "emp-1")

            chain.eq.assert_called_once_with("id", "input-1")
            chain.eq.return_value.eq.assert_called_once_with("employee_id", "emp-1")
