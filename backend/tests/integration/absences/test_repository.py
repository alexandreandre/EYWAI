"""
Tests d'intégration du repository absences (SupabaseAbsenceRepository).

Avec DB de test (fixture db_session) : opérations CRUD réelles contre absence_requests.
Sans DB : mock de supabase pour valider les appels (create, get_by_id, update, list_by_status,
list_validated_for_employees, list_by_employee_id).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.infrastructure.repository import (
    SupabaseAbsenceRepository,
    absence_repository,
)


pytestmark = pytest.mark.integration


class TestSupabaseAbsenceRepositoryCreate:
    """Repository create()."""

    def test_create_calls_insert_with_data_and_returns_first_row(self):
        """create() appelle supabase.table('absence_requests').insert(data).execute() et retourne data[0]."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            inserted = [
                {
                    "id": "req-new",
                    "employee_id": "emp-1",
                    "company_id": "comp-1",
                    "type": "conge_paye",
                    "status": "pending",
                    "selected_days": ["2025-06-10"],
                }
            ]
            chain.execute.return_value = MagicMock(data=inserted)
            table_mock.insert.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            data = {
                "employee_id": "emp-1",
                "company_id": "comp-1",
                "type": "conge_paye",
                "status": "pending",
                "selected_days": ["2025-06-10"],
            }
            result = repo.create(data)

            table_mock.insert.assert_called_once_with(data)
            assert result == inserted[0]
            assert result["id"] == "req-new"

    def test_create_raises_runtime_error_when_no_data_returned(self):
        """Si execute() ne retourne pas de data → RuntimeError."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[])
            table_mock.insert.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            with pytest.raises(RuntimeError, match="Échec de la création"):
                repo.create({"employee_id": "emp-1", "company_id": "c1", "type": "rtt", "status": "pending", "selected_days": []})


class TestSupabaseAbsenceRepositoryGetById:
    """Repository get_by_id()."""

    def test_get_by_id_returns_none_when_not_found(self):
        """get_by_id() avec id inconnu → None."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data=None)
            )
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.get_by_id("req-unknown")

            assert result is None
            table_mock.select.assert_called_once_with("*")
            chain.eq.assert_called_once_with("id", "req-unknown")

    def test_get_by_id_returns_row_when_found(self):
        """get_by_id() avec id existant → dict de la ligne."""
        row = {
            "id": "req-1",
            "employee_id": "emp-1",
            "type": "conge_paye",
            "status": "pending",
        }
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data=row)
            )
            table_mock.select.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.get_by_id("req-1")

            assert result == row


class TestSupabaseAbsenceRepositoryUpdate:
    """Repository update()."""

    def test_update_returns_none_when_no_row_updated(self):
        """update() si aucune ligne modifiée → None."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            update_chain = MagicMock()
            update_chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table_mock.update.return_value = update_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.update("req-1", {"status": "cancelled"})

            assert result is None

    def test_update_returns_updated_row_when_success(self):
        """update() appelle update puis select pour retourner la ligne à jour."""
        updated_row = {
            "id": "req-1",
            "employee_id": "emp-1",
            "status": "validated",
            "jours_payes": 2,
        }
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            update_chain = MagicMock()
            update_chain.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "req-1"}]
            )
            table_mock.update.return_value = update_chain
            select_chain = MagicMock()
            select_chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=updated_row
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.update("req-1", {"status": "validated", "jours_payes": 2})

            assert result == updated_row
            table_mock.update.assert_called_once_with(
                {"status": "validated", "jours_payes": 2}
            )


class TestSupabaseAbsenceRepositoryListByStatus:
    """Repository list_by_status()."""

    def test_list_by_status_returns_empty_list_when_no_data(self):
        """list_by_status() sans résultat → []."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            select_chain = MagicMock()
            select_chain.order.return_value.execute.return_value = MagicMock(
                data=None
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.list_by_status(None)

            assert result == []

    def test_list_by_status_with_filter_calls_eq_status(self):
        """list_by_status('pending') → query avec .eq('status', 'pending')."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[]
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            repo.list_by_status("pending")

            table_mock.select.assert_called_once()
            select_chain.eq.assert_called_once_with("status", "pending")


class TestSupabaseAbsenceRepositoryListValidatedForEmployees:
    """Repository list_validated_for_employees()."""

    def test_list_validated_for_employees_empty_ids_returns_empty(self):
        """list_validated_for_employees([]) → []."""
        repo = SupabaseAbsenceRepository()
        result = repo.list_validated_for_employees([])
        assert result == []

    def test_list_validated_for_employees_calls_in_and_eq_status(self):
        """Vérifie les appels in_('employee_id', ids) et eq('status', 'validated')."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            select_chain = MagicMock()
            select_chain.in_.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"employee_id": "emp-1", "type": "conge_paye", "selected_days": [], "jours_payes": 5}]
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.list_validated_for_employees(["emp-1", "emp-2"])

            assert len(result) == 1
            select_chain.in_.assert_called_once_with("employee_id", ["emp-1", "emp-2"])
            select_chain.in_.return_value.eq.assert_called_once_with(
                "status", "validated"
            )


class TestSupabaseAbsenceRepositoryListByEmployeeId:
    """Repository list_by_employee_id()."""

    def test_list_by_employee_id_returns_empty_when_none_data(self):
        """list_by_employee_id() sans données → []."""
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=None
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.list_by_employee_id("emp-1")

            assert result == []

    def test_list_by_employee_id_returns_list_ordered_by_created_at_desc(self):
        """list_by_employee_id() retourne les lignes et appelle order('created_at', desc=True)."""
        data = [
            {"id": "req-2", "employee_id": "emp-1", "created_at": "2025-06-02"},
            {"id": "req-1", "employee_id": "emp-1", "created_at": "2025-06-01"},
        ]
        with patch(
            "app.modules.absences.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=data
            )
            table_mock.select.return_value = select_chain
            supabase.table.return_value = table_mock

            repo = SupabaseAbsenceRepository()
            result = repo.list_by_employee_id("emp-1")

            assert result == data
            select_chain.eq.assert_called_once_with("employee_id", "emp-1")
            select_chain.eq.return_value.order.assert_called_once_with(
                "created_at", desc=True
            )


class TestAbsenceRepositorySingleton:
    """Vérification du singleton absence_repository."""

    def test_absence_repository_is_instance_of_supabase_repo(self):
        """absence_repository est une instance de SupabaseAbsenceRepository."""
        assert isinstance(absence_repository, SupabaseAbsenceRepository)
