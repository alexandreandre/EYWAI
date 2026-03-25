"""
Tests d'intégration du repository mutuelle_types (SupabaseMutuelleTypeRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans company_mutuelle_types, employee_mutuelle_types pour des tests CRUD réels.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.infrastructure.repository import (
    SupabaseMutuelleTypeRepository,
)


pytestmark = pytest.mark.integration

COMPANY_UUID_1 = "550e8400-e29b-41d4-a716-446655440000"
COMPANY_UUID_2 = "660e8400-e29b-41d4-a716-446655440001"


def _row(company_id: str = COMPANY_UUID_1, **kwargs):
    base = {
        "id": str(uuid4()),
        "company_id": company_id,
        "libelle": "Formule test",
        "montant_salarial": 50.0,
        "montant_patronal": 30.0,
        "part_patronale_soumise_a_csg": True,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": None,
    }
    base.update(kwargs)
    return base


class TestSupabaseMutuelleTypeRepositoryListByCompany:
    """list_by_company."""

    def test_list_by_company_calls_select_eq_order(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                _row(COMPANY_UUID_1, libelle="Formule A"),
                _row(COMPANY_UUID_1, libelle="Formule B"),
            ]
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.list_by_company(COMPANY_UUID_1)

        table.select.assert_called_once_with("*")
        chain.eq.assert_called_once_with("company_id", COMPANY_UUID_1)
        chain.eq.return_value.order.assert_called_once_with("libelle")
        assert len(result) == 2
        assert all(isinstance(e, MutuelleType) for e in result)
        assert result[0].libelle == "Formule A"
        assert result[1].libelle == "Formule B"

    def test_list_by_company_empty_data_returns_empty_list(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.list_by_company(COMPANY_UUID_1)

        assert result == []


class TestSupabaseMutuelleTypeRepositoryGetById:
    """get_by_id."""

    def test_get_by_id_with_company_filters_by_company(self):
        mt_id = str(uuid4())
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=_row(COMPANY_UUID_1, id=mt_id, libelle="Formule X")
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.get_by_id(mt_id, COMPANY_UUID_1)

        assert result is not None
        assert result.libelle == "Formule X"
        chain.eq.assert_any_call("id", mt_id)
        chain.eq.return_value.eq.assert_called_once_with("company_id", COMPANY_UUID_1)

    def test_get_by_id_without_company_does_not_filter_company(self):
        mt_id = str(uuid4())
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=_row(COMPANY_UUID_1, id=mt_id)
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.get_by_id(mt_id, None)

        assert result is not None
        chain.eq.assert_called_once_with("id", mt_id)

    def test_get_by_id_no_data_returns_none(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=None
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.get_by_id("770e8400-e29b-41d4-a716-446655440003", COMPANY_UUID_1)

        assert result is None


class TestSupabaseMutuelleTypeRepositoryFindByCompanyAndLibelle:
    """find_by_company_and_libelle."""

    def test_find_by_company_and_libelle_returns_entity_when_found(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[_row(COMPANY_UUID_1, libelle="Formule Unique")]
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.find_by_company_and_libelle(COMPANY_UUID_1, "Formule Unique")

        assert result is not None
        assert result.libelle == "Formule Unique"
        chain.eq.assert_any_call("company_id", COMPANY_UUID_1)
        chain.eq.return_value.eq.assert_called_once_with("libelle", "Formule Unique")

    def test_find_by_company_and_libelle_with_exclude_id_uses_neq(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.neq.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.find_by_company_and_libelle(
            COMPANY_UUID_1, "Libellé", exclude_id="exclude-uuid"
        )

        assert result is None
        chain.eq.return_value.eq.return_value.neq.assert_called_once_with(
            "id", "exclude-uuid"
        )


class TestSupabaseMutuelleTypeRepositoryCreate:
    """create."""

    def test_create_calls_insert_with_entity_data(self):
        mock_supabase = MagicMock()

        company_id = uuid4()
        entity = MutuelleType(
            id=None,
            company_id=company_id,
            libelle="Nouvelle formule",
            montant_salarial=60.0,
            montant_patronal=40.0,
            part_patronale_soumise_a_csg=True,
            is_active=True,
            created_at=None,
            updated_at=None,
            created_by=None,
        )
        new_id = str(uuid4())
        inserted_row = _row(
            str(company_id),
            id=new_id,
            libelle="Nouvelle formule",
            montant_salarial=60.0,
            montant_patronal=40.0,
        )
        table = MagicMock()
        table.insert.return_value.execute.return_value = MagicMock(data=[inserted_row])
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.create(entity, "user-uuid")

        table.insert.assert_called_once()
        call_row = table.insert.call_args[0][0]
        assert call_row["company_id"] == str(company_id)
        assert call_row["libelle"] == "Nouvelle formule"
        assert call_row["montant_salarial"] == 60.0
        assert call_row["created_by"] == "user-uuid"
        assert result.libelle == "Nouvelle formule"
        assert result.montant_salarial == 60.0


class TestSupabaseMutuelleTypeRepositoryUpdate:
    """update."""

    def test_update_calls_update_eq_execute(self):
        mt_id = str(uuid4())
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[
                _row(
                    COMPANY_UUID_1,
                    id=mt_id,
                    libelle="Mis à jour",
                    montant_salarial=70.0,
                    montant_patronal=45.0,
                )
            ]
        )
        table.update.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.update(
            mt_id,
            {
                "libelle": "Mis à jour",
                "montant_salarial": 70.0,
                "montant_patronal": 45.0,
            },
        )

        table.update.assert_called_once()
        call_data = table.update.call_args[0][0]
        assert call_data["libelle"] == "Mis à jour"
        assert call_data["montant_salarial"] == 70.0
        chain.eq.assert_called_once_with("id", mt_id)
        assert result is not None
        assert result.libelle == "Mis à jour"


class TestSupabaseMutuelleTypeRepositoryDelete:
    """delete."""

    def test_delete_calls_delete_eq_execute(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        table.delete.return_value = chain
        chain.eq.return_value.execute.return_value = None
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.delete("mt-123")

        table.delete.assert_called_once()
        chain.eq.assert_called_once_with("id", "mt-123")
        assert result is True


class TestSupabaseMutuelleTypeRepositoryListEmployeeIds:
    """list_employee_ids."""

    def test_list_employee_ids_returns_ids_from_employee_mutuelle_types(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[{"employee_id": "emp-1"}, {"employee_id": "emp-2"}]
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.list_employee_ids("mt-1")

        table.select.assert_called_once_with("employee_id")
        chain.eq.assert_called_once_with("mutuelle_type_id", "mt-1")
        assert result == ["emp-1", "emp-2"]


class TestSupabaseMutuelleTypeRepositoryValidateEmployeeIds:
    """validate_employee_ids_belong_to_company."""

    def test_validate_employee_ids_returns_subset_belonging_to_company(self):
        mock_supabase = MagicMock()
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"id": "emp-1"}, {"id": "emp-2"}]
        )
        table.select.return_value = chain
        mock_supabase.table.return_value = table

        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.validate_employee_ids_belong_to_company(
            COMPANY_UUID_1, ["emp-1", "emp-2", "emp-invalid"]
        )

        assert result == ["emp-1", "emp-2"]
        chain.eq.assert_called_once_with("company_id", COMPANY_UUID_1)

    def test_validate_employee_ids_empty_input_returns_empty(self):
        mock_supabase = MagicMock()
        repo = SupabaseMutuelleTypeRepository(mock_supabase)
        result = repo.validate_employee_ids_belong_to_company(COMPANY_UUID_1, [])
        assert result == []
