"""
Tests unitaires du service applicatif users.

Délégation aux règles du domain et aux repositories/providers.
Dépendances mockées.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules.users.application import service as user_service


pytestmark = pytest.mark.unit


# ----- check_role_hierarchy (délègue domain.rules) -----


class TestServiceCheckRoleHierarchy:
    """check_role_hierarchy(creator_user, target_role, company_id)."""

    def test_delegates_to_domain_rules(self):
        creator = MagicMock()
        creator.is_super_admin = True
        with patch("app.modules.users.application.service.domain_rules") as rules:
            rules.check_role_hierarchy.return_value = True
            result = user_service.check_role_hierarchy(creator, "rh", "c1")
            assert result is True
            rules.check_role_hierarchy.assert_called_once_with(creator, "rh", "c1")


# ----- has_any_rh_permission -----


class TestServiceHasAnyRhPermission:
    """has_any_rh_permission(user_id, company_id)."""

    def test_delegates_to_repository(self):
        with patch.object(
            user_service.user_permission_repository,
            "has_any_rh_permission",
            return_value=True,
        ) as mock_has:
            result = user_service.has_any_rh_permission("u1", "c1")
            assert result is True
            mock_has.assert_called_once_with("u1", "c1")

    def test_returns_false_when_repo_returns_false(self):
        with patch.object(
            user_service.user_permission_repository,
            "has_any_rh_permission",
            return_value=False,
        ):
            result = user_service.has_any_rh_permission("u1", "c1")
            assert result is False


# ----- copy_template_permissions_to_user -----


class TestServiceCopyTemplatePermissionsToUser:
    """copy_template_permissions_to_user(template_id, user_id, company_id, granted_by)."""

    def test_calls_repository_copy_from_template(self):
        with patch.object(
            user_service.user_permission_repository,
            "copy_from_template",
        ) as mock_copy:
            user_service.copy_template_permissions_to_user(
                "t1", "u1", "c1", "granted-by-u2"
            )
            mock_copy.assert_called_once_with("t1", "u1", "c1", "granted-by-u2")


# ----- get_default_system_template_id -----


class TestServiceGetDefaultSystemTemplateId:
    """get_default_system_template_id(base_role)."""

    def test_delegates_to_role_template_repository(self):
        with patch.object(
            user_service.role_template_repository,
            "get_default_system_template_id",
            return_value="template-uuid-1",
        ) as mock_get:
            result = user_service.get_default_system_template_id("rh")
            assert result == "template-uuid-1"
            mock_get.assert_called_once_with("rh")

    def test_returns_none_when_repo_returns_none(self):
        with patch.object(
            user_service.role_template_repository,
            "get_default_system_template_id",
            return_value=None,
        ):
            result = user_service.get_default_system_template_id("custom")
            assert result is None


# ----- get_credentials_logo_path -----


class TestServiceGetCredentialsLogoPath:
    """get_credentials_logo_path() -> Path."""

    def test_returns_path_from_provider(self):
        with patch.object(
            user_service.credentials_pdf_provider,
            "get_logo_path",
            return_value="/some/logo.png",
        ):
            result = user_service.get_credentials_logo_path()
            assert isinstance(result, Path)
            assert str(result) == "/some/logo.png"


# ----- Getters repositories / providers -----


class TestServiceGetters:
    """Vérification que les getters retournent les instances du module."""

    def test_get_user_repository_returns_repository(self):
        repo = user_service.get_user_repository()
        assert repo is user_service.user_repository

    def test_get_user_company_access_repository_returns_repository(self):
        repo = user_service.get_user_company_access_repository()
        assert repo is user_service.user_company_access_repository

    def test_get_company_repository_returns_repository(self):
        repo = user_service.get_company_repository()
        assert repo is user_service.company_repository

    def test_get_user_permission_repository_returns_repository(self):
        repo = user_service.get_user_permission_repository()
        assert repo is user_service.user_permission_repository

    def test_get_auth_provider_returns_provider(self):
        provider = user_service.get_auth_provider()
        assert provider is user_service.auth_provider

    def test_get_credentials_pdf_provider_returns_provider(self):
        provider = user_service.get_credentials_pdf_provider()
        assert provider is user_service.credentials_pdf_provider

    def test_get_storage_provider_returns_provider(self):
        provider = user_service.get_storage_provider()
        assert provider is user_service.storage_provider
