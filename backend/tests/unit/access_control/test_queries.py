"""
Tests unitaires des queries access_control (application/queries.py).

Repositories et service mockés : check_hierarchy, check_permission,
get_permission_categories, get_permission_actions, get_all_permissions,
get_permissions_matrix, get_user_permissions_summary, get_role_templates,
get_role_template_by_id.
"""

from uuid import UUID

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.access_control.application import queries
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


class TestCheckHierarchy:
    """check_hierarchy(current_user, target_role, company_id)."""

    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_returns_result_from_service(self, mock_service: MagicMock):
        """Délègue au service et retourne RoleHierarchyCheckResult."""
        mock_service.check_role_hierarchy_access.return_value = True
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

        result = queries.check_hierarchy(user, "rh", "company-1")

        mock_service.check_role_hierarchy_access.assert_called_once_with(
            user, "rh", "company-1"
        )
        assert result.is_allowed is True
        assert result.creator_role == "admin"
        assert result.target_role == "rh"
        assert result.company_id == "company-1"

    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_super_admin_creator_role_is_super_admin(self, mock_service: MagicMock):
        """Pour super_admin, creator_role dans le résultat est super_admin."""
        mock_service.check_role_hierarchy_access.return_value = True
        user = _make_user(is_super_admin=True, accessible_companies=[])

        result = queries.check_hierarchy(user, "admin", "company-1")

        assert result.creator_role == "super_admin"


class TestCheckPermission:
    """check_permission(user_id, company_id, permission_code)."""

    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_returns_result_when_has_permission(self, mock_service: MagicMock):
        """Retourne PermissionCheckResult avec has_permission=True si le service dit oui."""
        mock_service.check_user_has_permission.return_value = True

        result = queries.check_permission("user-1", "company-1", "payslips.create")

        mock_service.check_user_has_permission.assert_called_once_with(
            "user-1", "company-1", "payslips.create"
        )
        assert result.has_permission is True
        assert result.permission_code == "payslips.create"
        assert result.user_id == "user-1"
        assert result.company_id == "company-1"

    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_returns_result_when_no_permission(self, mock_service: MagicMock):
        """Retourne has_permission=False si le service dit non."""
        mock_service.check_user_has_permission.return_value = False

        result = queries.check_permission("user-1", "company-1", "payslips.delete")

        assert result.has_permission is False


class TestGetPermissionCategories:
    """get_permission_categories(current_user)."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    def test_returns_list_of_permission_category(self, mock_reader: MagicMock):
        """Retourne liste de PermissionCategory à partir des rows du reader."""
        from app.modules.access_control.schemas import PermissionCategory

        mock_reader.get_permission_categories_active.return_value = [
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "code": "payslips",
                "label": "Bulletins",
                "description": None,
                "display_order": 1,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        user = _make_user()

        result = queries.get_permission_categories(user)

        mock_reader.get_permission_categories_active.assert_called_once()
        assert len(result) == 1
        assert isinstance(result[0], PermissionCategory)
        assert result[0].code == "payslips"
        assert result[0].label == "Bulletins"


class TestGetPermissionActions:
    """get_permission_actions(current_user)."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    def test_returns_list_of_permission_action(self, mock_reader: MagicMock):
        """Retourne liste de PermissionAction."""

        mock_reader.get_permission_actions_active.return_value = [
            {
                "id": "20000000-0000-0000-0000-000000000001",
                "code": "create",
                "label": "Créer",
                "description": None,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        user = _make_user()

        result = queries.get_permission_actions(user)

        mock_reader.get_permission_actions_active.assert_called_once()
        assert len(result) == 1
        assert result[0].code == "create"


class TestGetAllPermissions:
    """get_all_permissions(current_user, category_id?, required_role?)."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    def test_returns_permissions_with_filters(self, mock_reader: MagicMock):
        """Passe les filtres au reader et retourne liste de Permission."""

        mock_reader.get_permissions_active.return_value = []
        user = _make_user()

        queries.get_all_permissions(user, category_id="cat-1", required_role="rh")

        mock_reader.get_permissions_active.assert_called_once_with(
            category_id="cat-1", required_role="rh"
        )

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    def test_returns_mapped_permissions(self, mock_reader: MagicMock):
        """Retourne des Permission construites depuis les rows."""

        mock_reader.get_permissions_active.return_value = [
            {
                "id": "30000000-0000-0000-0000-000000000001",
                "category_id": "10000000-0000-0000-0000-000000000001",
                "action_id": "20000000-0000-0000-0000-000000000001",
                "code": "payslips.create",
                "label": "Créer bulletin",
                "required_role": "rh",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        user = _make_user()

        result = queries.get_all_permissions(user)

        assert len(result) == 1
        assert result[0].code == "payslips.create"


class TestGetPermissionsMatrix:
    """get_permissions_matrix(current_user, company_id, user_id?)."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_raises_403_when_no_rh_access(
        self, mock_service: MagicMock, mock_reader: MagicMock
    ):
        """Lève 403 si l'utilisateur n'a pas accès RH à l'entreprise."""
        mock_service.can_access_company_as_rh.return_value = False
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            queries.get_permissions_matrix(user, "company-1")
        assert exc_info.value.status_code == 403
        assert "Accès RH requis" in str(exc_info.value.detail)
        mock_reader.get_permission_categories_active.assert_not_called()

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_returns_matrix_with_categories_and_granted_flags(
        self, mock_service: MagicMock, mock_reader: MagicMock
    ):
        """Retourne PermissionMatrix avec catégories et is_granted par permission."""
        from app.modules.access_control.schemas import PermissionMatrix

        mock_service.can_access_company_as_rh.return_value = True
        mock_reader.get_permission_categories_active.return_value = [
            {"id": "cat-1", "code": "payslips", "label": "Paie", "description": None},
        ]
        mock_reader.get_permissions_for_matrix.return_value = [
            {
                "id": "perm-1",
                "code": "payslips.create",
                "label": "Créer",
                "category_id": "cat-1",
                "action_id": "act-1",
                "required_role": "rh",
                "is_active": True,
            },
        ]
        mock_reader.get_permission_actions_active.return_value = [
            {"id": "act-1", "code": "create", "label": "Créer"},
        ]
        mock_reader.get_user_permission_ids.return_value = {"perm-1"}  # granted
        user = _make_user()

        result = queries.get_permissions_matrix(user, "company-1")

        assert isinstance(result, PermissionMatrix)
        assert len(result.categories) == 1
        assert result.categories[0].code == "payslips"
        assert len(result.categories[0].actions) == 1
        assert result.categories[0].actions[0]["is_granted"] is True


class TestGetUserPermissionsSummary:
    """get_user_permissions_summary(current_user, user_id, company_id)."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_raises_404_when_no_access(
        self, mock_service: MagicMock, mock_reader: MagicMock
    ):
        """Lève 404 si l'utilisateur cible n'a pas d'accès à l'entreprise."""
        mock_reader.get_user_company_access.return_value = None
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            queries.get_user_permissions_summary(user, "target-user", "company-1")
        assert exc_info.value.status_code == 404
        assert "pas d'accès" in str(exc_info.value.detail)

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_raises_403_when_target_not_viewable(
        self, mock_service: MagicMock, mock_reader: MagicMock
    ):
        """Lève 403 si le créateur n'est pas autorisé à voir les perms de l'utilisateur cible."""
        mock_reader.get_user_company_access.return_value = {
            "role": "admin",
            "role_templates": {},
        }
        mock_service.get_viewable_roles.return_value = [
            "rh",
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]
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
        # rh ne peut pas "voir" admin
        with pytest.raises(HTTPException) as exc_info:
            queries.get_user_permissions_summary(user, "target-user", "company-1")
        assert exc_info.value.status_code == 403
        assert "autorisé à voir" in str(exc_info.value.detail)

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_returns_summary_for_viewable_user(
        self, mock_service: MagicMock, mock_reader: MagicMock
    ):
        """Retourne UserPermissionsSummary quand accès et hiérarchie OK."""
        from app.modules.access_control.schemas import UserPermissionsSummary

        target_user_id = "00000000-0000-0000-0000-000000000001"
        target_company_id = "00000000-0000-0000-0000-000000000002"
        mock_reader.get_user_company_access.return_value = {
            "role": "rh",
            "role_template_id": "50000000-0000-0000-0000-000000000001",
            "role_templates": {"name": "Template RH"},
        }
        mock_service.get_viewable_roles.return_value = [
            "admin",
            "rh",
            "collaborateur_rh",
            "collaborateur",
            "custom",
        ]
        mock_reader.get_user_permission_ids.return_value = []
        mock_reader.get_permissions_details_by_ids.return_value = []
        user = _make_user(
            accessible_companies=[
                CompanyAccess(
                    company_id=target_company_id,
                    company_name="C1",
                    role="admin",
                    is_primary=True,
                ),
            ]
        )
        user.active_company_id = target_company_id

        result = queries.get_user_permissions_summary(
            user, target_user_id, target_company_id
        )

        assert isinstance(result, UserPermissionsSummary)
        assert result.base_role == "rh"
        assert result.role_template_name == "Template RH"
        assert result.user_id == UUID(target_user_id)
        assert result.company_id == UUID(target_company_id)


class TestGetRoleTemplates:
    """get_role_templates(current_user, company_id?, base_role?, include_system?)."""

    @patch("app.modules.access_control.application.queries.role_template_repository")
    def test_returns_list_with_permissions_count(self, mock_repo: MagicMock):
        """Appelle le repo et enrichit chaque template avec permissions_count."""

        mock_repo.get_role_templates_list.return_value = [
            {
                "id": "40000000-0000-0000-0000-000000000001",
                "name": "Template 1",
                "description": None,
                "job_title": "RH",
                "base_role": "rh",
                "is_system": False,
                "is_active": True,
                "company_id": "00000000-0000-0000-0000-000000000001",
                "created_by": "00000000-0000-0000-0000-000000000002",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        mock_repo.get_role_template_permissions_count.return_value = 5
        user = _make_user()

        result = queries.get_role_templates(user, company_id="company-1")

        mock_repo.get_role_templates_list.assert_called_once_with(
            company_id="company-1", base_role=None, include_system=True
        )
        assert len(result) == 1
        assert result[0].name == "Template 1"
        assert result[0].permissions_count == 5


class TestGetRoleTemplateById:
    """get_role_template_by_id(current_user, template_id)."""

    @patch("app.modules.access_control.application.queries.role_template_repository")
    def test_raises_404_when_not_found(self, mock_repo: MagicMock):
        """Lève 404 si le template n'existe pas."""
        mock_repo.get_role_template_by_id.return_value = None
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            queries.get_role_template_by_id(user, "missing-id")
        assert exc_info.value.status_code == 404
        assert "Template non trouvé" in str(exc_info.value.detail)

    @patch("app.modules.access_control.application.queries.role_template_repository")
    def test_returns_template_with_permissions(self, mock_repo: MagicMock):
        """Retourne RoleTemplateWithPermissions avec liste des permissions."""
        from app.modules.access_control.schemas import RoleTemplateWithPermissions

        mock_repo.get_role_template_by_id.return_value = {
            "id": "40000000-0000-0000-0000-000000000001",
            "name": "Template",
            "description": None,
            "job_title": "RH",
            "base_role": "rh",
            "is_system": False,
            "is_active": True,
            "company_id": "00000000-0000-0000-0000-000000000001",
            "created_by": "00000000-0000-0000-0000-000000000002",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        mock_repo.get_role_template_permission_details.return_value = [
            {
                "id": "10000000-0000-0000-0000-000000000001",
                "code": "payslips.create",
                "label": "Créer",
                "category_id": "20000000-0000-0000-0000-000000000001",
                "action_id": "30000000-0000-0000-0000-000000000001",
                "required_role": "rh",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        user = _make_user()

        result = queries.get_role_template_by_id(user, "tpl-1")

        assert isinstance(result, RoleTemplateWithPermissions)
        assert result.name == "Template"
        assert result.permissions_count == 1
        assert len(result.permissions) == 1
