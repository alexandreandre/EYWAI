"""
Tests d'intégration du repository access_control.

SupabasePermissionRepository : user_has_permission, user_has_any_rh_permission.
Fonctions infrastructure (queries) : get_permission_categories_active,
get_permissions_active, get_role_templates_list, role_template_name_exists,
create_role_template, attach_permissions_to_role_template, etc.

Avec DB de test (fixture db_session) ou mocks Supabase pour valider la logique et les appels.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.access_control.infrastructure.repository import (
    SupabasePermissionRepository,
)
from app.modules.access_control.infrastructure.queries import (
    get_permission_categories_active,
    get_permission_actions_active,
    get_permissions_active,
    get_user_permission_ids,
    get_user_company_access,
    get_role_templates_list,
    get_role_template_by_id,
    get_role_template_permissions_count,
    role_template_name_exists,
    create_role_template,
    attach_permissions_to_role_template,
)


@pytest.mark.integration
class TestSupabasePermissionRepository:
    """SupabasePermissionRepository : user_has_permission, user_has_any_rh_permission."""

    def test_user_has_permission_returns_true_when_permission_found(self):
        """user_has_permission retourne True si une ligne user_permissions a la permission active."""
        with patch(
            "app.modules.access_control.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "up-1",
                        "permissions": {
                            "code": "payslips.create",
                            "is_active": True,
                        },
                    },
                ]
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabasePermissionRepository()
            result = repo.user_has_permission("user-1", "company-1", "payslips.create")

        assert result is True
        supabase.table.assert_called_with("user_permissions")
        table_mock.select.assert_called_once()

    def test_user_has_permission_returns_false_when_no_match(self):
        """user_has_permission retourne False si code ne correspond pas ou is_active False."""
        with patch(
            "app.modules.access_control.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "up-1",
                        "permissions": {"code": "other.permission", "is_active": True},
                    },
                ]
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabasePermissionRepository()
            result = repo.user_has_permission("user-1", "company-1", "payslips.create")

        assert result is False

    def test_user_has_permission_returns_false_when_empty_data(self):
        """user_has_permission retourne False si pas de données."""
        with patch(
            "app.modules.access_control.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(data=[])
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabasePermissionRepository()
            result = repo.user_has_permission("user-1", "company-1", "payslips.create")

        assert result is False

    def test_user_has_any_rh_permission_returns_true_when_rh_permission_exists(self):
        """user_has_any_rh_permission True si une permission a required_role in (rh, admin)."""
        with patch(
            "app.modules.access_control.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(
                data=[
                    {"permissions": {"required_role": "rh", "is_active": True}},
                ]
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabasePermissionRepository()
            result = repo.user_has_any_rh_permission("user-1", "company-1")

        assert result is True

    def test_user_has_any_rh_permission_returns_false_when_no_rh_permission(self):
        """user_has_any_rh_permission False si aucune permission rh/admin."""
        with patch(
            "app.modules.access_control.infrastructure.repository.supabase"
        ) as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock(
                data=[
                    {
                        "permissions": {
                            "required_role": "collaborateur",
                            "is_active": True,
                        }
                    },
                ]
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = SupabasePermissionRepository()
            result = repo.user_has_any_rh_permission("user-1", "company-1")

        assert result is False


@pytest.mark.integration
class TestPermissionCatalogQueries:
    """Fonctions de lecture du catalogue (permission_categories, permission_actions, permissions)."""

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_permission_categories_active_returns_list(self, supabase_mock):
        """get_permission_categories_active appelle la table et retourne une liste."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=[{"id": "c1", "code": "payslips", "is_active": True}]
        )
        table_mock.select.return_value.eq.return_value.order.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_permission_categories_active()

        assert isinstance(result, list)
        supabase_mock.table.assert_called_with("permission_categories")
        table_mock.select.assert_called_once_with("*")
        table_mock.select.return_value.eq.assert_called_with("is_active", True)

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_permission_actions_active_returns_list(self, supabase_mock):
        """get_permission_actions_active retourne une liste triée par label."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        table_mock.select.return_value.eq.return_value.order.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_permission_actions_active()

        assert isinstance(result, list)
        supabase_mock.table.assert_called_with("permission_actions")

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_permissions_active_with_filters(self, supabase_mock):
        """get_permissions_active applique category_id et required_role si fournis."""
        table_mock = MagicMock()
        order_chain = MagicMock()
        order_chain.execute.return_value = MagicMock(data=[])
        table_mock.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value = order_chain
        supabase_mock.table.return_value = table_mock

        result = get_permissions_active(category_id="cat-1", required_role="rh")

        assert isinstance(result, list)
        assert result == []
        table_mock.select.assert_called_once_with("*")
        table_mock.select.return_value.eq.assert_called_with("is_active", True)


@pytest.mark.integration
class TestUserPermissionQueries:
    """get_user_permission_ids, get_user_company_access."""

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_user_permission_ids_returns_set_of_ids(self, supabase_mock):
        """get_user_permission_ids retourne un set de permission_id."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=[{"permission_id": "p1"}, {"permission_id": "p2"}]
        )
        table_mock.select.return_value.eq.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_user_permission_ids("user-1", "company-1")

        assert result == {"p1", "p2"}
        supabase_mock.table.assert_called_with("user_permissions")

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_user_company_access_returns_none_when_empty(self, supabase_mock):
        """get_user_company_access retourne None si pas d'accès."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        table_mock.select.return_value.eq.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_user_company_access("user-1", "company-1")

        assert result is None

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_user_company_access_returns_first_row_when_exists(self, supabase_mock):
        """get_user_company_access retourne la première ligne si accès existant."""
        row = {"user_id": "u1", "company_id": "c1", "role": "rh", "role_templates": {}}
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[row])
        table_mock.select.return_value.eq.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_user_company_access("user-1", "company-1")

        assert result == row


@pytest.mark.integration
class TestRoleTemplateQueries:
    """get_role_templates_list, get_role_template_by_id, count, name_exists, create, attach."""

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_role_templates_list_with_company_and_system(self, supabase_mock):
        """get_role_templates_list avec company_id et include_system fusionne system + company templates."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[]),
        ]
        table_mock.select.return_value.eq.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_role_templates_list(company_id="company-1", include_system=True)

        assert isinstance(result, list)
        assert result == []
        assert supabase_mock.table.call_count >= 1

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_role_template_by_id_returns_none_when_not_found(self, supabase_mock):
        """get_role_template_by_id retourne None si aucun template."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        table_mock.select.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_role_template_by_id("missing-id")

        assert result is None

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_get_role_template_permissions_count_returns_count(self, supabase_mock):
        """get_role_template_permissions_count retourne le count de la requête."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(count=3)
        table_mock.select.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = get_role_template_permissions_count("tpl-1")

        assert result == 3
        supabase_mock.table.assert_called_with("role_template_permissions")

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_role_template_name_exists_returns_true_when_found(self, supabase_mock):
        """role_template_name_exists True si au moins une ligne."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[{"id": "t1"}])
        table_mock.select.return_value.eq.return_value.eq.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = role_template_name_exists("company-1", "Mon Template")

        assert result is True
        table_mock.select.return_value.eq.return_value.eq.assert_called_with(
            "name", "Mon Template"
        )

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_create_role_template_calls_insert_and_returns_id(self, supabase_mock):
        """create_role_template insert et retourne l'id du template créé."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(
            data=[{"id": "550e8400-e29b-41d4-a716-446655440000"}]
        )
        table_mock.insert.return_value = chain
        supabase_mock.table.return_value = table_mock

        result = create_role_template(
            company_id="company-1",
            name="Template",
            description="Desc",
            job_title="RH",
            base_role="rh",
            created_by="user-1",
        )

        assert result == "550e8400-e29b-41d4-a716-446655440000"
        table_mock.insert.assert_called_once()
        call_data = table_mock.insert.call_args[0][0]
        assert call_data["name"] == "Template"
        assert call_data["base_role"] == "rh"
        assert call_data["is_system"] is False
        assert call_data["is_active"] is True

    @patch("app.modules.access_control.infrastructure.queries.supabase")
    def test_attach_permissions_to_role_template_inserts_per_template(
        self, supabase_mock
    ):
        """attach_permissions_to_role_template fait un insert par permission_id."""
        table_mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock()
        table_mock.insert.return_value = chain
        supabase_mock.table.return_value = table_mock

        attach_permissions_to_role_template("tpl-1", ["perm-1", "perm-2"])

        assert table_mock.insert.call_count == 2
        calls = table_mock.insert.call_args_list
        assert calls[0][0][0]["template_id"] == "tpl-1"
        assert calls[0][0][0]["permission_id"] == "perm-1"
        assert calls[1][0][0]["permission_id"] == "perm-2"
