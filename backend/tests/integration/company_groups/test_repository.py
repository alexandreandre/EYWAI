"""
Tests d'intégration du repository company_groups (CompanyGroupRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : prévoir la fixture db_session (conftest) et des données
dans company_groups, companies (group_id), user_company_accesses pour des tests CRUD réels.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.modules.company_groups.infrastructure.repository import (
    CompanyGroupRepository,
)
from app.modules.company_groups.infrastructure.queries import (
    fetch_group_by_id_with_companies,
    fetch_groups_with_companies,
    fetch_company_ids_by_group_id,
)

pytestmark = pytest.mark.integration

TEST_GROUP_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_COMPANY_ID = "660e8400-e29b-41d4-a716-446655440001"


class TestCompanyGroupRepositoryCreate:
    """create."""

    def test_create_calls_insert_and_returns_row(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            inserted = {
                "id": TEST_GROUP_ID,
                "group_name": "Nouveau Groupe",
                "siren": "123456789",
                "description": None,
                "logo_url": None,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": None,
            }
            table.insert.return_value.execute.return_value = MagicMock(data=[inserted])
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.create({
                "group_name": "Nouveau Groupe",
                "siren": "123456789",
                "description": None,
                "logo_url": None,
                "is_active": True,
            })

            table.insert.assert_called_once()
            call_data = table.insert.call_args[0][0]
            assert call_data["group_name"] == "Nouveau Groupe"
            assert call_data["siren"] == "123456789"
            assert result == inserted

    def test_create_returns_none_when_no_data(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            table.insert.return_value.execute.return_value = MagicMock(data=[])
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.create({"group_name": "G", "is_active": True})
            assert result is None


class TestCompanyGroupRepositoryUpdate:
    """update."""

    def test_update_calls_update_eq_id_and_returns_row(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            updated = {
                "id": TEST_GROUP_ID,
                "group_name": "Groupe Mis à Jour",
                "siren": None,
                "is_active": True,
                "created_at": None,
                "updated_at": datetime.now().isoformat(),
            }
            chain.eq.return_value.execute.return_value = MagicMock(data=[updated])
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.update(TEST_GROUP_ID, {"group_name": "Groupe Mis à Jour"})

            table.update.assert_called_once()
            chain.eq.assert_called_once_with("id", TEST_GROUP_ID)
            assert result == updated

    def test_update_returns_none_when_no_match(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.update("unknown-id", {"group_name": "X"})
            assert result is None


class TestCompanyGroupRepositoryExists:
    """exists."""

    def test_exists_returns_true_when_data(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[{"id": TEST_GROUP_ID}])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            assert repo.exists(TEST_GROUP_ID) is True
            table.select.assert_called_once_with("id")
            chain.eq.assert_called_once_with("id", TEST_GROUP_ID)

    def test_exists_returns_false_when_no_data(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            assert repo.exists(TEST_GROUP_ID) is False


class TestCompanyGroupRepositorySetCompanyGroup:
    """set_company_group et set_company_group_with_current."""

    def test_set_company_group_calls_update_companies(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[{"id": TEST_COMPANY_ID}])
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.set_company_group(TEST_COMPANY_ID, TEST_GROUP_ID)

            table.update.assert_called_once_with({"group_id": TEST_GROUP_ID})
            chain.eq.assert_called_once_with("id", TEST_COMPANY_ID)
            assert result is True

    def test_set_company_group_with_current_adds_eq_when_current_group_id(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": TEST_COMPANY_ID}]
            )
            table.update.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.set_company_group_with_current(
                TEST_COMPANY_ID, None, TEST_GROUP_ID
            )

            chain.eq.assert_any_call("id", TEST_COMPANY_ID)
            chain.eq.return_value.eq.assert_called_once_with("group_id", TEST_GROUP_ID)
            assert result is True


class TestFetchGroupByIdWithCompanies:
    """Infrastructure query fetch_group_by_id_with_companies."""

    def test_returns_row_when_found(self):
        with patch(
            "app.modules.company_groups.infrastructure.queries.supabase"
        ) as supabase:
            chain = MagicMock()
            row = {
                "id": TEST_GROUP_ID,
                "group_name": "G1",
                "companies": [{"id": TEST_COMPANY_ID, "company_name": "C1"}],
            }
            chain.eq.return_value.execute.return_value = MagicMock(data=[row])
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = fetch_group_by_id_with_companies(TEST_GROUP_ID)
            assert result == row
            chain.select.assert_called_once()
            chain.eq.assert_called_once_with("id", TEST_GROUP_ID)

    def test_returns_none_when_not_found(self):
        with patch(
            "app.modules.company_groups.infrastructure.queries.supabase"
        ) as supabase:
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = fetch_group_by_id_with_companies("unknown")
            assert result is None


class TestFetchGroupsWithCompanies:
    """Infrastructure query fetch_groups_with_companies."""

    def test_without_company_ids_selects_all_active(self):
        with patch(
            "app.modules.company_groups.infrastructure.queries.supabase"
        ) as supabase:
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            chain.select.return_value = chain
            supabase.table.return_value = chain

            fetch_groups_with_companies(None)
            chain.eq.assert_called_once_with("is_active", True)

    def test_with_company_ids_calls_in_and_eq_then_execute(self):
        """Avec company_ids, la requête utilise .in_(companies.id) et .eq(is_active)."""
        with patch(
            "app.modules.company_groups.infrastructure.queries.supabase"
        ) as supabase:
            chain = MagicMock()
            chain.select.return_value = chain
            chain.in_.return_value = chain
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            supabase.table.return_value = chain

            result = fetch_groups_with_companies(["c1", "c2"])
            chain.select.assert_called_once()
            chain.in_.assert_called_once_with("companies.id", ["c1", "c2"])
            chain.eq.assert_called_with("is_active", True)
            assert result == []


class TestFetchCompanyIdsByGroupId:
    """fetch_company_ids_by_group_id."""

    def test_returns_list_of_ids(self):
        with patch(
            "app.modules.company_groups.infrastructure.queries.supabase"
        ) as supabase:
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "c1"}, {"id": "c2"}]
            )
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = fetch_company_ids_by_group_id(TEST_GROUP_ID)
            assert result == ["c1", "c2"]


class TestRepositoryGetGroupsWithCompanyAndEffectif:
    """get_groups_with_company_and_effectif (enrichit company_count, total_employees)."""

    def test_enriches_each_group_with_count_and_effectif(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.fetch_company_effectif_by_group_id"
        ) as fetch_effectif:
            fetch_effectif.side_effect = [
                [{"id": "c1", "effectif": 5}, {"id": "c2", "effectif": 10}],
                [{"id": "c3", "effectif": 3}],
            ]
            repo = CompanyGroupRepository()
            groups = [
                {"id": "g1", "group_name": "G1", "description": None, "created_at": None},
                {"id": "g2", "group_name": "G2", "description": None, "created_at": None},
            ]
            result = repo.get_groups_with_company_and_effectif(groups)

            assert len(result) == 2
            assert result[0]["company_count"] == 2
            assert result[0]["total_employees"] == 15
            assert result[1]["company_count"] == 1
            assert result[1]["total_employees"] == 3


class TestRepositoryUserAccesses:
    """get_user_accesses_for_companies, get_existing_user_accesses, delete_user_company_accesses."""

    def test_get_existing_user_accesses_returns_company_to_role_map(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[
                    {"company_id": "c1", "role": "admin"},
                    {"company_id": "c2", "role": "rh"},
                ]
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.get_existing_user_accesses("u1", ["c1", "c2"])
            assert result == {"c1": "admin", "c2": "rh"}

    def test_delete_user_company_accesses_returns_count(self):
        with patch(
            "app.modules.company_groups.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(
                data=[{}, {}]
            )
            table.delete.return_value = chain
            supabase.table.return_value = table

            repo = CompanyGroupRepository()
            result = repo.delete_user_company_accesses("u1", ["c1", "c2"])
            assert result == 2
