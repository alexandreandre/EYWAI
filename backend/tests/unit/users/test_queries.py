"""
Tests unitaires des requêtes (queries) du module users.

Chaque query est testée avec repositories et infra mockés.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.users.application import queries
from app.modules.users.schemas.responses import CompanyAccess, User, UserDetail


pytestmark = pytest.mark.unit


def _user_super_admin():
    return User(
        id="sa-1",
        email="super@example.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _user_with_companies():
    return User(
        id="u1",
        email="user@example.com",
        first_name="Jean",
        last_name="Dupont",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id="c1",
                company_name="Société A",
                role="admin",
                is_primary=True,
            ),
            CompanyAccess(
                company_id="c2",
                company_name="Société B",
                role="rh",
                is_primary=False,
            ),
        ],
        active_company_id="c1",
    )


# ----- get_my_companies -----


class TestGetMyCompanies:
    """get_my_companies(current_user)."""

    @patch("app.modules.users.application.queries.infra_queries")
    def test_super_admin_returns_active_companies_from_infra(self, infra_queries):
        infra_queries.fetch_active_companies_with_groups.return_value = [
            {"id": "c1", "company_name": "Comp1", "siret": None},
        ]
        current = _user_super_admin()

        result = queries.get_my_companies(current)

        assert len(result) == 1
        assert result[0].company_id == "c1"
        assert result[0].company_name == "Comp1"
        assert result[0].role == "super_admin"
        infra_queries.fetch_active_companies_with_groups.assert_called_once()

    def test_non_super_admin_returns_accessible_companies(self):
        current = _user_with_companies()

        result = queries.get_my_companies(current)

        assert result == current.accessible_companies
        assert len(result) == 2
        assert result[0].company_id == "c1"
        assert result[0].role == "admin"


# ----- get_me -----


class TestGetMe:
    """get_me(current_user)."""

    def test_returns_current_user(self):
        current = _user_with_companies()
        result = queries.get_me(current)
        assert result is current
        assert result.id == "u1"
        assert result.email == "user@example.com"


# ----- get_user_company_accesses -----


class TestGetUserCompanyAccesses:
    """get_user_company_accesses(user_id, current_user)."""

    @patch("app.modules.users.application.queries.infra_queries")
    def test_super_admin_gets_any_user_accesses(self, infra_queries):
        infra_queries.fetch_user_accesses_with_companies.return_value = [
            {
                "company_id": "c1",
                "role": "rh",
                "is_primary": True,
                "companies": {"id": "c1", "company_name": "Société", "siret": None},
            },
        ]
        current = _user_super_admin()

        result = queries.get_user_company_accesses("other-user-id", current)

        assert len(result) == 1
        assert result[0].company_id == "c1"
        assert result[0].role == "rh"

    @patch("app.modules.users.application.queries.infra_queries")
    def test_non_super_admin_own_id_gets_accesses(self, infra_queries):
        infra_queries.fetch_user_accesses_with_companies.return_value = [
            {
                "company_id": "c1",
                "role": "admin",
                "is_primary": True,
                "companies": {"id": "c1", "company_name": "Ma Société", "siret": None},
            },
        ]
        current = _user_with_companies()

        result = queries.get_user_company_accesses("u1", current)

        assert len(result) == 1

    @patch("app.modules.users.application.queries.infra_queries")
    def test_non_super_admin_other_user_not_admin_raises_permission_error(self, infra_queries):
        infra_queries.fetch_target_user_company_ids.return_value = ["c99"]
        current = _user_with_companies()

        with pytest.raises(PermissionError) as exc_info:
            queries.get_user_company_accesses("other-user", current)
        assert "permissions" in str(exc_info.value).lower() or "pas" in str(exc_info.value).lower()


# ----- get_company_users -----


class TestGetCompanyUsers:
    """get_company_users(company_id, role, current_user)."""

    @patch("app.modules.users.application.queries.get_auth_provider")
    @patch("app.modules.users.application.queries.infra_queries")
    def test_returns_mapped_user_details(self, infra_queries, get_auth_provider):
        infra_queries.fetch_company_users_rows.return_value = [
            {
                "user_id": "u1",
                "role": "rh",
                "role_template_id": None,
                "role_templates": None,
                "profiles": {
                    "id": "u1",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "job_title": "RH",
                    "created_at": None,
                },
            },
        ]
        auth = MagicMock()
        auth.get_user_by_id.return_value = MagicMock(user=MagicMock(email="jean@example.com"))
        get_auth_provider.return_value = auth
        current = _user_super_admin()

        result = queries.get_company_users("c1", None, current)

        assert len(result) == 1
        assert isinstance(result[0], UserDetail)
        assert result[0].id == "u1"
        assert result[0].email == "jean@example.com"
        assert result[0].first_name == "Jean"
        assert result[0].role == "rh"

    @patch("app.modules.users.application.queries.get_auth_provider")
    @patch("app.modules.users.application.queries.infra_queries")
    def test_filters_by_viewable_roles(self, infra_queries, get_auth_provider):
        infra_queries.fetch_company_users_rows.return_value = [
            {
                "user_id": "u1",
                "role": "collaborateur",
                "role_templates": None,
                "profiles": {"id": "u1", "first_name": "A", "last_name": "B", "job_title": None, "created_at": None},
            },
        ]
        auth = MagicMock()
        auth.get_user_by_id.return_value = MagicMock(user=MagicMock(email="a@b.com"))
        get_auth_provider.return_value = auth
        current = _user_with_companies()

        result = queries.get_company_users("c1", None, current)

        assert len(result) == 1
        assert result[0].role == "collaborateur"


# ----- get_accessible_companies_for_user_creation -----


class TestGetAccessibleCompaniesForUserCreation:
    """get_accessible_companies_for_user_creation(current_user)."""

    @patch("app.modules.users.application.queries.infra_queries")
    def test_super_admin_gets_all_active_companies(self, infra_queries):
        infra_queries.fetch_active_companies_for_creation.return_value = [
            {"id": "c1", "company_name": "Comp1"},
        ]
        current = _user_super_admin()

        result = queries.get_accessible_companies_for_user_creation(current)

        assert len(result) == 1
        assert result[0]["company_id"] == "c1"
        assert result[0]["company_name"] == "Comp1"
        assert "admin" in result[0]["can_create_roles"]

    @patch("app.modules.users.application.queries.get_company_repository")
    def test_rh_gets_companies_with_can_create_roles(self, get_company_repository):
        get_company_repository.return_value.get_name.return_value = "Ma Société"
        current = _user_with_companies()

        result = queries.get_accessible_companies_for_user_creation(current)

        assert len(result) >= 1
        for item in result:
            assert "company_id" in item
            assert "can_create_roles" in item


# ----- get_user_detail -----


class TestGetUserDetail:
    """get_user_detail(user_id, company_id, current_user)."""

    @patch("app.modules.users.application.queries.get_auth_provider")
    @patch("app.modules.users.application.queries.get_user_permission_repository")
    @patch("app.modules.users.application.queries.get_user_repository")
    @patch("app.modules.users.application.queries.get_user_company_access_repository")
    def test_returns_detail_dict(
        self, get_access_repo, get_user_repo, get_perm_repo, get_auth_provider
    ):
        get_access_repo.return_value.get_by_user_and_company_with_template.return_value = {
            "role": "rh",
            "role_template_id": "t1",
            "role_templates": {"name": "Responsable RH"},
        }
        get_user_repo.return_value.get_by_id.return_value = {
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "RH",
        }
        get_perm_repo.return_value.get_permission_ids.return_value = ["p1", "p2"]
        auth = MagicMock()
        auth.get_user_by_id.return_value = MagicMock(user=MagicMock(email="jean@example.com"))
        get_auth_provider.return_value = auth
        current = _user_super_admin()

        result = queries.get_user_detail("u1", "c1", current)

        assert result["id"] == "u1"
        assert result["email"] == "jean@example.com"
        assert result["first_name"] == "Jean"
        assert result["role"] == "rh"
        assert result["permission_ids"] == ["p1", "p2"]
        assert result["can_edit"] is True

    @patch("app.modules.users.application.queries.get_user_company_access_repository")
    def test_no_access_raises_lookup_error(self, get_access_repo):
        get_access_repo.return_value.get_by_user_and_company_with_template.return_value = None
        current = _user_super_admin()

        with pytest.raises(LookupError) as exc_info:
            queries.get_user_detail("u1", "c1", current)
        assert "n'a pas d'accès" in str(exc_info.value)
