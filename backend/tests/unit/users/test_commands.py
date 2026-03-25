"""
Tests unitaires des commandes du module users.

Chaque commande est testée avec repositories et providers mockés (patch sur
app.modules.users.application.commands ou service).
"""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from app.modules.users.application import commands
from app.modules.users.application.dto import (
    GrantAccessResult,
    RevokeAccessResult,
    SetPrimaryCompanyResult,
    UpdateAccessResult,
)


pytestmark = pytest.mark.unit


def _current_user(id_="user-1", is_super_admin=False):
    u = MagicMock()
    u.id = id_
    u.is_super_admin = is_super_admin
    return u


# ----- set_primary_company -----


class TestSetPrimaryCompany:
    """set_primary_company(user_id, company_id, current_user)."""

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_success_returns_result(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.get_by_user_and_company.return_value = {
            "company_id": "c1",
            "is_primary": True,
        }

        result = commands.set_primary_company("u1", "c1", _current_user())

        assert isinstance(result, SetPrimaryCompanyResult)
        assert result.company_id == "c1"
        assert "succès" in result.message
        access_repo.set_primary.assert_called_once_with("u1", "c1")
        access_repo.get_by_user_and_company.assert_called_once_with("u1", "c1")

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_access_not_found_raises_lookup_error(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.get_by_user_and_company.return_value = None

        with pytest.raises(LookupError) as exc_info:
            commands.set_primary_company("u1", "c1", _current_user())
        assert "Accès non trouvé" in str(exc_info.value)


# ----- grant_company_access_by_email -----


class TestGrantCompanyAccessByEmail:
    """grant_company_access_by_email(user_email, company_id, role, is_primary, current_user)."""

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_user_not_found_raises_lookup_error(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_email.return_value = None
        with pytest.raises(LookupError) as exc_info:
            commands.grant_company_access_by_email(
                "unknown@example.com", "c1", "rh", False, _current_user()
            )
        assert "Utilisateur non trouvé" in str(exc_info.value)

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_company_not_found_raises_lookup_error(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_email.return_value = {"id": "u1"}
        get_company_repo.return_value.get_name.return_value = None

        with pytest.raises(LookupError) as exc_info:
            commands.grant_company_access_by_email(
                "user@example.com", "bad-company", "rh", False, _current_user()
            )
        assert "Entreprise non trouvée" in str(exc_info.value)

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_grant_new_access_returns_success(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_email.return_value = {"id": "u1"}
        get_company_repo.return_value.get_name.return_value = "Ma Société"
        get_access_repo.return_value.get_by_user_and_company.return_value = None
        get_access_repo.return_value.create.return_value = {
            "user_id": "u1",
            "company_id": "c1",
        }

        result = commands.grant_company_access_by_email(
            "user@example.com", "c1", "rh", True, _current_user()
        )

        assert isinstance(result, GrantAccessResult)
        assert "accordé" in result.message.lower() or "succès" in result.message.lower()
        assert result.access is not None
        get_access_repo.return_value.create.assert_called_once()

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_update_existing_access_returns_success(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_email.return_value = {"id": "u1"}
        get_company_repo.return_value.get_name.return_value = "Ma Société"
        get_access_repo.return_value.get_by_user_and_company.return_value = {
            "role": "collaborateur"
        }
        get_access_repo.return_value.update.return_value = {
            "user_id": "u1",
            "company_id": "c1",
            "role": "rh",
        }

        result = commands.grant_company_access_by_email(
            "user@example.com", "c1", "rh", False, _current_user()
        )

        assert (
            "mis à jour" in result.message.lower() or "succès" in result.message.lower()
        )
        get_access_repo.return_value.update.assert_called_once()


# ----- grant_company_access_by_user_id -----


class TestGrantCompanyAccessByUserId:
    """grant_company_access_by_user_id(user_id, company_id, role, is_primary, current_user)."""

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_user_not_found_raises_lookup_error(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_id.return_value = None

        with pytest.raises(LookupError) as exc_info:
            commands.grant_company_access_by_user_id(
                "unknown-uuid", "c1", "rh", False, _current_user()
            )
        assert "Utilisateur non trouvé" in str(exc_info.value)

    @patch("app.modules.users.application.commands.get_company_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_grant_creates_access(
        self, get_user_repo, get_access_repo, get_company_repo
    ):
        get_user_repo.return_value.get_by_id.return_value = {"id": "u1"}
        get_company_repo.return_value.get_name.return_value = "Société"
        get_access_repo.return_value.get_by_user_and_company.return_value = None
        get_access_repo.return_value.create.return_value = {
            "user_id": "u1",
            "company_id": "c1",
        }

        result = commands.grant_company_access_by_user_id(
            "u1", "c1", "collaborateur_rh", True, _current_user()
        )

        assert isinstance(result, GrantAccessResult)
        get_access_repo.return_value.create.assert_called_once()


# ----- revoke_company_access -----


class TestRevokeCompanyAccess:
    """revoke_company_access(user_id, company_id, current_user)."""

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_revoke_success_returns_result(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.count_admins.return_value = 2
        access_repo.delete.return_value = {"user_id": "u1", "company_id": "c1"}

        result = commands.revoke_company_access("u1", "c1", _current_user())

        assert isinstance(result, RevokeAccessResult)
        assert result.user_id == "u1"
        assert result.company_id == "c1"
        assert "révoqué" in result.message.lower() or "succès" in result.message.lower()

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_revoke_last_admin_self_raises_value_error(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.count_admins.return_value = 1
        current = _current_user(id_="u1", is_super_admin=False)

        with pytest.raises(ValueError) as exc_info:
            commands.revoke_company_access("u1", "c1", current)
        assert "dernier admin" in str(exc_info.value).lower()

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_revoke_super_admin_self_ok_even_if_last_admin(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.count_admins.return_value = 1
        access_repo.delete.return_value = {"user_id": "u1", "company_id": "c1"}
        current = _current_user(id_="u1", is_super_admin=True)

        result = commands.revoke_company_access("u1", "c1", current)
        assert result.user_id == "u1"

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_revoke_access_not_found_raises_lookup_error(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.count_admins.return_value = 2
        access_repo.delete.return_value = None

        with pytest.raises(LookupError) as exc_info:
            commands.revoke_company_access("u1", "c1", _current_user())
        assert "Accès non trouvé" in str(exc_info.value)


# ----- update_company_access -----


class TestUpdateCompanyAccess:
    """update_company_access(user_id, company_id, role, is_primary, current_user)."""

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_no_modification_raises_value_error(self, get_repo):
        with pytest.raises(ValueError) as exc_info:
            commands.update_company_access("u1", "c1", None, None, _current_user())
        assert "Aucune modification" in str(exc_info.value)

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_update_role_success(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.update.return_value = {
            "user_id": "u1",
            "company_id": "c1",
            "role": "rh",
        }

        result = commands.update_company_access("u1", "c1", "rh", None, _current_user())

        assert isinstance(result, UpdateAccessResult)
        assert result.access["role"] == "rh"
        access_repo.update.assert_called_once_with("u1", "c1", {"role": "rh"})

    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    def test_update_access_not_found_raises_lookup_error(self, get_repo):
        access_repo = MagicMock()
        get_repo.return_value = access_repo
        access_repo.update.return_value = None

        with pytest.raises(LookupError) as exc_info:
            commands.update_company_access("u1", "c1", "rh", None, _current_user())
        assert "Accès non trouvé" in str(exc_info.value)


# ----- update_user_with_permissions -----


class TestUpdateUserWithPermissions:
    """update_user_with_permissions(user_id, data, current_user)."""

    @patch("app.modules.users.application.commands.get_user_permission_repository")
    @patch("app.modules.users.application.commands.get_user_company_access_repository")
    @patch("app.modules.users.application.commands.get_user_repository")
    def test_no_access_to_company_raises_lookup_error(
        self, get_user_repo, get_access_repo, get_perm_repo
    ):
        get_access_repo.return_value.get_by_user_and_company.return_value = None
        data = MagicMock()
        data.company_id = UUID("660e8400-e29b-41d4-a716-446655440001")
        data.first_name = None
        data.last_name = None
        data.job_title = None
        data.base_role = None
        data.role_template_id = None
        data.permission_ids = None

        with pytest.raises(LookupError) as exc_info:
            commands.update_user_with_permissions("u1", data, _current_user())
        assert "n'a pas d'accès" in str(exc_info.value)
