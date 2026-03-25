"""
Tests d'intégration du repository bonus_types (SupabaseBonusTypeRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans company_bonus_types pour des tests CRUD réels.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.infrastructure.repository import (
    SupabaseBonusTypeRepository,
)


pytestmark = pytest.mark.integration

# UUIDs valides : row_to_bonus_type utilise _parse_uuid sur id et company_id
COMPANY_UUID_1 = "550e8400-e29b-41d4-a716-446655440000"
COMPANY_UUID_2 = "660e8400-e29b-41d4-a716-446655440001"


def _row(company_id: str = COMPANY_UUID_1, **kwargs):
    base = {
        "id": str(uuid4()),
        "company_id": company_id,
        "libelle": "Prime test",
        "type": "montant_fixe",
        "montant": 100.0,
        "seuil_heures": None,
        "soumise_a_cotisations": True,
        "soumise_a_impot": True,
        "prompt_ia": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": None,
        "created_by": None,
    }
    base.update(kwargs)
    return base


class TestSupabaseBonusTypeRepositoryListByCompany:
    """list_by_company."""

    def test_list_by_company_calls_select_eq_order(self):
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[
                    _row(COMPANY_UUID_1, libelle="Prime A"),
                    _row(COMPANY_UUID_1, libelle="Prime B"),
                ]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.list_by_company(COMPANY_UUID_1)

            table.select.assert_called_once_with("*")
            chain.eq.assert_called_once_with("company_id", COMPANY_UUID_1)
            chain.eq.return_value.order.assert_called_once_with("libelle")
            assert len(result) == 2
            assert all(isinstance(e, BonusType) for e in result)
            assert result[0].libelle == "Prime A"
            assert result[1].libelle == "Prime B"

    def test_list_by_company_empty_data_returns_empty_list(self):
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.order.return_value.execute.return_value = MagicMock(
                data=[]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.list_by_company(COMPANY_UUID_1)

            assert result == []


class TestSupabaseBonusTypeRepositoryGetById:
    """get_by_id."""

    def test_get_by_id_with_company_filters_by_company(self):
        bt_id = str(uuid4())
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=_row(COMPANY_UUID_1, id=bt_id, libelle="Prime X")
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.get_by_id(bt_id, COMPANY_UUID_1)

            assert result is not None
            assert result.libelle == "Prime X"
            # Premier eq("id", ...), puis .eq.return_value.eq("company_id", ...)
            chain.eq.assert_called_once_with("id", bt_id)
            chain.eq.return_value.eq.assert_called_once_with(
                "company_id", COMPANY_UUID_1
            )

    def test_get_by_id_without_company_does_not_filter_company(self):
        bt_id = str(uuid4())
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data=_row(COMPANY_UUID_1, id=bt_id))
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.get_by_id(bt_id, None)

            assert result is not None
            chain.eq.assert_called_once_with("id", bt_id)

    def test_get_by_id_no_data_returns_none(self):
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            # Deux .eq() sont appelés (id puis company_id), donc eq.return_value.eq.return_value
            chain.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.get_by_id(
                "770e8400-e29b-41d4-a716-446655440003", COMPANY_UUID_1
            )

            assert result is None


class TestSupabaseBonusTypeRepositoryCreate:
    """create."""

    def test_create_calls_insert_with_entity_data(self):
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            company_id = uuid4()
            user_id = uuid4()
            new_bt_id = str(uuid4())
            entity = BonusType(
                id=None,
                company_id=company_id,
                libelle="Nouvelle prime",
                type=BonusTypeKind.MONTANT_FIXE,
                montant=200.0,
                seuil_heures=None,
                soumise_a_cotisations=True,
                soumise_a_impot=True,
                prompt_ia=None,
                created_by=user_id,
            )
            inserted_row = _row(
                str(company_id), id=new_bt_id, libelle="Nouvelle prime", montant=200.0
            )
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(
                data=[inserted_row]
            )
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.create(entity)

            table.insert.assert_called_once()
            call_row = table.insert.call_args[0][0]
            assert call_row["company_id"] == str(company_id)
            assert call_row["libelle"] == "Nouvelle prime"
            assert call_row["montant"] == 200.0
            assert call_row["created_by"] == str(user_id)
            assert result.libelle == "Nouvelle prime"
            assert result.montant == 200.0


class TestSupabaseBonusTypeRepositoryUpdate:
    """update."""

    def test_update_calls_update_eq_execute(self):
        bt_id = str(uuid4())
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(
                data=[
                    _row(COMPANY_UUID_1, id=bt_id, libelle="Mis à jour", montant=150.0)
                ]
            )
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.update(bt_id, {"libelle": "Mis à jour", "montant": 150.0})

            table.update.assert_called_once()
            call_data = table.update.call_args[0][0]
            assert call_data["libelle"] == "Mis à jour"
            assert call_data["montant"] == 150.0
            chain.eq.assert_called_once_with("id", bt_id)
            assert result is not None
            assert result.libelle == "Mis à jour"

    def test_update_filters_none_values(self):
        bt_id = str(uuid4())
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            repo.update(bt_id, {"libelle": "X", "montant": None})

            call_data = table.update.call_args[0][0]
            assert "libelle" in call_data
            # None values are filtered out by the repository
            assert "montant" not in call_data


class TestSupabaseBonusTypeRepositoryDelete:
    """delete."""

    def test_delete_calls_delete_eq_execute(self):
        with patch(
            "app.modules.bonus_types.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.delete.return_value = chain
            chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = SupabaseBonusTypeRepository()
            result = repo.delete("bt-123")

            table.delete.assert_called_once()
            chain.eq.assert_called_once_with("id", "bt-123")
            assert result is True
