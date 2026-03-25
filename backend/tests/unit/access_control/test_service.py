"""
Tests unitaires du service access_control (application/service.py).

AccessControlService avec IPermissionRepository mocké : hiérarchie des rôles,
vérification des permissions, accès RH, require_rh_access, require_rh_access_for_company,
can_access_company_as_rh, get_viewable_roles.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.access_control.application.service import (
    AccessControlService,
    get_access_control_service,
)
from app.modules.users.schemas.responses import CompanyAccess, User


def _make_user(
    user_id: str = "user-1",
    is_super_admin: bool = False,
    accessible_companies: list | None = None,
) -> User:
    if accessible_companies is None:
        accessible_companies = [
            CompanyAccess(
                company_id="company-1", company_name="C1", role="rh", is_primary=True
            ),
        ]
    return User(
        id=user_id,
        email="user@example.com",
        first_name="Test",
        last_name="User",
        is_super_admin=is_super_admin,
        accessible_companies=accessible_companies,
        active_company_id="company-1",
    )


class TestGetAccessControlService:
    """get_access_control_service(repository?)."""

    def test_returns_service_with_default_repository_when_none(self):
        """Sans argument, retourne un service (repository par défaut)."""
        svc = get_access_control_service()
        assert isinstance(svc, AccessControlService)
        assert svc._perms is not None

    def test_returns_service_with_injected_repository(self):
        """Avec un repository fourni, l'utilise pour les permissions."""
        mock_repo = MagicMock()
        svc = get_access_control_service(permission_repository=mock_repo)
        assert svc._perms is mock_repo


class TestCheckRoleHierarchyAccess:
    """check_role_hierarchy_access(creator_user, target_role, company_id)."""

    def test_super_admin_can_assign_any_role(self):
        """Super admin peut tout attribuer."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(is_super_admin=True, accessible_companies=[])

        assert svc.check_role_hierarchy_access(user, "admin", "company-1") is True
        assert svc.check_role_hierarchy_access(user, "custom", "company-1") is True
        mock_repo.user_has_permission.assert_not_called()

    def test_admin_can_assign_rh(self):
        """Admin peut attribuer rh."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="admin",
                    is_primary=True,
                ),
            ]
        )

        assert svc.check_role_hierarchy_access(user, "rh", "company-1") is True

    def test_rh_cannot_assign_admin(self):
        """RH ne peut pas attribuer admin."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="rh",
                    is_primary=True,
                ),
            ]
        )

        assert svc.check_role_hierarchy_access(user, "admin", "company-1") is False

    def test_user_without_role_in_company_returns_false(self):
        """Utilisateur sans rôle dans l'entreprise → False."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="other-company",
                    company_name="Other",
                    role="admin",
                    is_primary=True,
                ),
            ]
        )

        assert svc.check_role_hierarchy_access(user, "rh", "company-1") is False


class TestCheckUserHasPermission:
    """check_user_has_permission(user_id, company_id, permission_code)."""

    def test_delegates_to_repository(self):
        """Délègue au repository et retourne le booléen."""
        mock_repo = MagicMock()
        mock_repo.user_has_permission.return_value = True
        svc = AccessControlService(mock_repo)

        result = svc.check_user_has_permission("user-1", "company-1", "payslips.create")

        mock_repo.user_has_permission.assert_called_once_with(
            "user-1", "company-1", "payslips.create"
        )
        assert result is True

    def test_returns_false_when_repository_returns_false(self):
        """Retourne False quand le repository retourne False."""
        mock_repo = MagicMock()
        mock_repo.user_has_permission.return_value = False
        svc = AccessControlService(mock_repo)

        assert (
            svc.check_user_has_permission("user-1", "company-1", "payslips.delete")
            is False
        )


class TestHasAnyRhPermission:
    """has_any_rh_permission(user_id, company_id)."""

    def test_delegates_to_repository(self):
        """Délègue au repository."""
        mock_repo = MagicMock()
        mock_repo.user_has_any_rh_permission.return_value = True
        svc = AccessControlService(mock_repo)

        result = svc.has_any_rh_permission("user-1", "company-1")

        mock_repo.user_has_any_rh_permission.assert_called_once_with(
            "user-1", "company-1"
        )
        assert result is True


class TestGetViewableRoles:
    """get_viewable_roles(creator_role)."""

    def test_returns_roles_from_domain_rules(self):
        """Délègue aux règles du domain (pas au repository)."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)

        roles = svc.get_viewable_roles("admin")
        assert "admin" in roles
        assert "rh" in roles
        assert "collaborateur" in roles

        roles_rh = svc.get_viewable_roles("rh")
        assert "rh" in roles_rh
        assert "admin" not in roles_rh

        mock_repo.user_has_permission.assert_not_called()


class TestRequireRhAccess:
    """require_rh_access(current_user)."""

    def test_super_admin_does_not_raise(self):
        """Super admin ne lève jamais."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(is_super_admin=True, accessible_companies=[])

        svc.require_rh_access(user)  # no raise

    def test_user_with_rh_in_any_company_does_not_raise(self):
        """Utilisateur avec accès RH dans au moins une entreprise ne lève pas."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="c1", company_name="C1", role="rh", is_primary=True
                ),
            ]
        )

        svc.require_rh_access(user)  # no raise

    def test_user_without_rh_raises_403(self):
        """Utilisateur sans aucun accès RH → 403."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="c1",
                    company_name="C1",
                    role="collaborateur",
                    is_primary=True,
                ),
            ]
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.require_rh_access(user)
        assert exc_info.value.status_code == 403
        assert "Accès RH requis" in str(exc_info.value.detail)


class TestRequireRhAccessForCompany:
    """require_rh_access_for_company(current_user, company_id)."""

    def test_super_admin_does_not_raise(self):
        """Super admin ne lève jamais."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(is_super_admin=True, accessible_companies=[])

        svc.require_rh_access_for_company(user, "any-company")  # no raise

    def test_user_with_rh_in_company_does_not_raise(self):
        """Utilisateur avec accès RH pour cette entreprise ne lève pas."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="rh",
                    is_primary=True,
                ),
            ]
        )

        svc.require_rh_access_for_company(user, "company-1")  # no raise

    def test_user_without_rh_for_company_raises_403(self):
        """Utilisateur sans accès RH pour cette entreprise → 403."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="collaborateur",
                    is_primary=True,
                ),
            ]
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.require_rh_access_for_company(user, "company-1")
        assert exc_info.value.status_code == 403


class TestCanAccessCompanyAsRh:
    """can_access_company_as_rh(current_user, company_id)."""

    def test_super_admin_returns_true(self):
        """Super admin a toujours accès RH."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(is_super_admin=True, accessible_companies=[])

        assert svc.can_access_company_as_rh(user, "any-company") is True
        mock_repo.user_has_any_rh_permission.assert_not_called()

    def test_admin_in_company_returns_true(self):
        """Rôle admin dans l'entreprise → True (règle pure)."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="admin",
                    is_primary=True,
                ),
            ]
        )

        assert svc.can_access_company_as_rh(user, "company-1") is True

    def test_rh_in_company_returns_true(self):
        """Rôle rh dans l'entreprise → True."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="rh",
                    is_primary=True,
                ),
            ]
        )

        assert svc.can_access_company_as_rh(user, "company-1") is True

    def test_collaborateur_returns_false(self):
        """Rôle collaborateur (sans custom) → False."""
        mock_repo = MagicMock()
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="collaborateur",
                    is_primary=True,
                ),
            ]
        )

        assert svc.can_access_company_as_rh(user, "company-1") is False

    def test_custom_with_rh_permission_returns_true(self):
        """Rôle custom avec au moins une permission RH (repository) → True."""
        mock_repo = MagicMock()
        mock_repo.user_has_any_rh_permission.return_value = True
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="custom",
                    is_primary=True,
                ),
            ]
        )

        assert svc.can_access_company_as_rh(user, "company-1") is True
        mock_repo.user_has_any_rh_permission.assert_called_once_with(
            "user-1", "company-1"
        )

    def test_custom_without_rh_permission_returns_false(self):
        """Rôle custom sans permission RH → False."""
        mock_repo = MagicMock()
        mock_repo.user_has_any_rh_permission.return_value = False
        svc = AccessControlService(mock_repo)
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id="company-1",
                    company_name="C1",
                    role="custom",
                    is_primary=True,
                ),
            ]
        )

        assert svc.can_access_company_as_rh(user, "company-1") is False
