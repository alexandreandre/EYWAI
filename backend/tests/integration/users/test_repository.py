"""
Tests d'intégration du repository users : opérations CRUD / métier.

Avec DB de test (fixture db_session) : tests réels contre les tables.
Sans DB : mocks Supabase pour valider la logique et les appels.
Le conftest fournit db_session (peut être None) ; si None, on utilise des mocks.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.users.infrastructure.repository import (
    SupabaseUserRepository,
    SupabaseUserCompanyAccessRepository,
    SupabaseCompanyRepository,
    SupabaseRoleTemplateRepository,
    SupabaseUserPermissionRepository,
)


pytestmark = pytest.mark.integration


# ----- SupabaseUserRepository -----


class TestSupabaseUserRepository:
    """Table profiles : get_by_id, get_by_email, create, update."""

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_by_id_returns_none_when_empty(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=[])
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserRepository()
        result = repo.get_by_id("unknown-id")

        assert result is None
        table.select.assert_called_once_with("*")
        chain.eq.assert_called_once_with("id", "unknown-id")

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_by_id_returns_row_when_found(self, supabase):
        row = {"id": "u1", "first_name": "Jean", "last_name": "Dupont"}
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=[row])
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserRepository()
        result = repo.get_by_id("u1")

        assert result == row

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_by_email_returns_none_when_empty(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=[])
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserRepository()
        result = repo.get_by_email("unknown@example.com")

        assert result is None

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_create_calls_insert_with_data(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        table.insert.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserRepository()
        repo.create({"id": "u1", "first_name": "Jean", "last_name": "Dupont"})

        table.insert.assert_called_once()
        call_data = table.insert.call_args[0][0]
        assert call_data["id"] == "u1"
        assert call_data["first_name"] == "Jean"

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_update_calls_update_then_eq_then_execute(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        table.update.return_value = chain
        chain.eq.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserRepository()
        repo.update("u1", {"first_name": "Updated"})

        table.update.assert_called_once_with({"first_name": "Updated"})
        chain.eq.assert_called_once_with("id", "u1")


# ----- SupabaseUserCompanyAccessRepository -----


class TestSupabaseUserCompanyAccessRepository:
    """Table user_company_accesses : get, create, update, delete, set_primary, count_admins."""

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_by_user_and_company_returns_none_when_empty(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserCompanyAccessRepository()
        result = repo.get_by_user_and_company("u1", "c1")

        assert result is None

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_by_user_and_company_returns_row_when_found(self, supabase):
        row = {"user_id": "u1", "company_id": "c1", "role": "rh", "is_primary": True}
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[row]
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserCompanyAccessRepository()
        result = repo.get_by_user_and_company("u1", "c1")

        assert result == row

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_create_returns_inserted_row(self, supabase):
        row = {"user_id": "u1", "company_id": "c1", "role": "rh"}
        table = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[row])
        table.insert.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserCompanyAccessRepository()
        result = repo.create({"user_id": "u1", "company_id": "c1", "role": "rh"})

        assert result == row

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_delete_returns_deleted_row(self, supabase):
        row = {"user_id": "u1", "company_id": "c1"}
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[row]
        )
        table.delete.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserCompanyAccessRepository()
        result = repo.delete("u1", "c1")

        assert result == row

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_count_admins_returns_count(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "u1"}, {"user_id": "u2"}]
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserCompanyAccessRepository()
        result = repo.count_admins("c1")

        assert result == 2


# ----- SupabaseCompanyRepository -----


class TestSupabaseCompanyRepository:
    """Table companies : get_name, get_active_with_groups, get_active_ids_and_names."""

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_name_returns_none_when_empty(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(data=[])
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseCompanyRepository()
        result = repo.get_name("unknown-id")

        assert result is None

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_name_returns_company_name_when_found(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.execute.return_value = MagicMock(
            data=[{"company_name": "Ma Société"}]
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseCompanyRepository()
        result = repo.get_name("c1")

        assert result == "Ma Société"


# ----- SupabaseRoleTemplateRepository -----


class TestSupabaseRoleTemplateRepository:
    """role_templates : get_default_system_template_id."""

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_default_system_template_id_returns_none_for_custom(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseRoleTemplateRepository()
        result = repo.get_default_system_template_id("custom")

        assert result is None

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_default_system_template_id_returns_id_for_rh(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[{"id": "template-uuid-1"}])
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseRoleTemplateRepository()
        result = repo.get_default_system_template_id("rh")

        assert result == "template-uuid-1"


# ----- SupabaseUserPermissionRepository -----


class TestSupabaseUserPermissionRepository:
    """user_permissions : get_permission_ids, copy_from_template, delete_for_user_company, upsert."""

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_get_permission_ids_returns_list(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"permission_id": "p1"}, {"permission_id": "p2"}]
        )
        table.select.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserPermissionRepository()
        result = repo.get_permission_ids("u1", "c1")

        assert set(result) == {"p1", "p2"}

    @patch("app.modules.users.infrastructure.repository.supabase")
    def test_delete_for_user_company_calls_delete(self, supabase):
        table = MagicMock()
        chain = MagicMock()
        table.delete.return_value = chain
        chain.eq.return_value = chain
        supabase.table.return_value = table

        repo = SupabaseUserPermissionRepository()
        repo.delete_for_user_company("u1", "c1")

        table.delete.assert_called_once()
        chain.eq.assert_any_call("user_id", "u1")
        chain.eq.assert_any_call("company_id", "c1")
