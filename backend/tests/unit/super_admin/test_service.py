"""
Tests du service applicatif du module super_admin (application/service.py).

Dépendances mockées : get_by_user_id (repository), row_to_super_admin / super_admin_to_row (mappers).
"""
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest

from app.modules.super_admin.application.service import (
    SuperAdminAccessError,
    verify_super_admin_and_return_row,
    require_can_create_companies as service_require_can_create,
    require_can_delete_companies as service_require_can_delete,
)
from app.modules.super_admin.domain.entities import SuperAdmin


USER_ID = "660e8400-e29b-41d4-a716-446655440001"
SUPER_ADMIN_ROW = {
    "id": "sa-id-1",
    "user_id": USER_ID,
    "email": "super@test.com",
    "first_name": "Super",
    "last_name": "Admin",
    "can_create_companies": True,
    "can_delete_companies": True,
    "can_view_all_data": True,
    "can_impersonate": False,
    "is_active": True,
}


class TestSuperAdminAccessError:
    """Exception SuperAdminAccessError."""

    def test_inherits_exception(self):
        """Hérite de Exception."""
        assert issubclass(SuperAdminAccessError, Exception)

    def test_message_preserved(self):
        """Message conservé."""
        exc = SuperAdminAccessError("Accès refusé")
        assert str(exc) == "Accès refusé"


class TestVerifySuperAdminAndReturnRow:
    """verify_super_admin_and_return_row."""

    def test_raises_when_not_super_admin(self):
        """Lève SuperAdminAccessError si get_by_user_id retourne None."""
        with patch(
            "app.modules.super_admin.application.service.get_by_user_id",
            return_value=None,
        ):
            with pytest.raises(SuperAdminAccessError) as exc_info:
                verify_super_admin_and_return_row(USER_ID)
        assert "super administrateur" in str(exc_info.value)

    def test_returns_row_when_super_admin_found(self):
        """Retourne le dict row quand un super admin actif existe."""
        entity = SuperAdmin(
            id=uuid4(),
            user_id=uuid4(),
            email="super@test.com",
            first_name="Super",
            last_name="Admin",
            can_create_companies=True,
            can_delete_companies=True,
            can_view_all_data=True,
            can_impersonate=False,
            is_active=True,
        )
        with patch(
            "app.modules.super_admin.application.service.get_by_user_id",
            return_value=entity,
        ):
            with patch(
                "app.modules.super_admin.application.service.super_admin_to_row",
                return_value=SUPER_ADMIN_ROW,
            ):
                row = verify_super_admin_and_return_row(USER_ID)
        assert row == SUPER_ADMIN_ROW
        assert row["user_id"] == USER_ID or row["email"] == "super@test.com"


class TestServiceRequireCanCreateCompanies:
    """require_can_create_companies (service)."""

    def test_passes_when_permission_true(self):
        """Ne lève pas si can_create_companies=True."""
        row = {**SUPER_ADMIN_ROW, "can_create_companies": True}
        with patch(
            "app.modules.super_admin.application.service.row_to_super_admin",
            return_value=MagicMock(can_create_companies=True),
        ):
            service_require_can_create(row)  # no raise

    def test_raises_super_admin_access_error_when_no_permission(self):
        """Lève SuperAdminAccessError si can_create_companies=False."""
        row = {**SUPER_ADMIN_ROW, "can_create_companies": False}
        with patch(
            "app.modules.super_admin.application.service.row_to_super_admin",
            return_value=MagicMock(can_create_companies=False),
        ):
            with pytest.raises(SuperAdminAccessError) as exc_info:
                service_require_can_create(row)
        assert "créer des entreprises" in str(exc_info.value)


class TestServiceRequireCanDeleteCompanies:
    """require_can_delete_companies (service)."""

    def test_passes_when_permission_true(self):
        """Ne lève pas si can_delete_companies=True."""
        row = {**SUPER_ADMIN_ROW, "can_delete_companies": True}
        with patch(
            "app.modules.super_admin.application.service.row_to_super_admin",
            return_value=MagicMock(can_delete_companies=True),
        ):
            service_require_can_delete(row)  # no raise

    def test_raises_super_admin_access_error_when_no_permission(self):
        """Lève SuperAdminAccessError si can_delete_companies=False."""
        row = {**SUPER_ADMIN_ROW, "can_delete_companies": False}
        with patch(
            "app.modules.super_admin.application.service.row_to_super_admin",
            return_value=MagicMock(can_delete_companies=False),
        ):
            with pytest.raises(SuperAdminAccessError) as exc_info:
                service_require_can_delete(row)
        assert "supprimer des entreprises" in str(exc_info.value)
