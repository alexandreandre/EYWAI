"""
Tests unitaires du service applicatif uploads (application/service.py).

Dépendance infra (can_edit_entity_logo) mockée pour isoler ensure_can_edit_entity_logo
et validate_logo_file.
"""
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.uploads.application.service import (
    ensure_can_edit_entity_logo,
    validate_logo_file,
)
from app.modules.uploads.domain.rules import ALLOWED_LOGO_MIMETYPES, MAX_LOGO_SIZE_BYTES
from app.modules.users.schemas.responses import User


def _make_user(
    user_id: str = "user-1",
    is_super_admin: bool = False,
) -> User:
    return User(
        id=user_id,
        email="user@test.com",
        first_name="Test",
        last_name="User",
        is_super_admin=is_super_admin,
        accessible_companies=[],
        active_company_id="company-1",
    )


class TestEnsureCanEditEntityLogo:
    """ensure_can_edit_entity_logo : vérification droits + entity_type."""

    def test_invalid_entity_type_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_entity_logo(
                entity_type="invalid",
                entity_id="id-1",
                current_user=_make_user(),
            )
        assert exc_info.value.status_code == 400
        assert "entity_type" in str(exc_info.value.detail)

    @patch("app.modules.uploads.application.service.infra_queries.can_edit_entity_logo")
    def test_company_not_allowed_raises_403(self, mock_can_edit):
        mock_can_edit.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_entity_logo(
                entity_type="company",
                entity_id="company-1",
                current_user=_make_user(),
            )
        assert exc_info.value.status_code == 403
        assert "administrateur" in str(exc_info.value.detail).lower()

    @patch("app.modules.uploads.application.service.infra_queries.can_edit_entity_logo")
    def test_group_not_allowed_raises_403_super_admin_message(self, mock_can_edit):
        mock_can_edit.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_entity_logo(
                entity_type="group",
                entity_id="group-1",
                current_user=_make_user(is_super_admin=False),
            )
        assert exc_info.value.status_code == 403
        assert "super administrateur" in str(exc_info.value.detail).lower()

    @patch("app.modules.uploads.application.service.infra_queries.can_edit_entity_logo")
    def test_allowed_does_not_raise(self, mock_can_edit):
        mock_can_edit.return_value = True

        ensure_can_edit_entity_logo(
            entity_type="company",
            entity_id="company-1",
            current_user=_make_user(),
        )
        mock_can_edit.assert_called_once_with(
            user_id="user-1",
            is_super_admin=False,
            entity_type="company",
            entity_id="company-1",
        )


class TestValidateLogoFile:
    """validate_logo_file : type MIME et taille."""

    def test_none_content_type_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_logo_file(None, 100)
        assert exc_info.value.status_code == 400
        assert "Type de fichier" in str(exc_info.value.detail) or "autorisé" in str(
            exc_info.value.detail
        )

    def test_disallowed_content_type_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_logo_file("application/pdf", 100)
        assert exc_info.value.status_code == 400
        allowed_str = ", ".join(sorted(ALLOWED_LOGO_MIMETYPES))
        assert allowed_str in str(exc_info.value.detail)

    def test_allowed_content_type_under_max_does_not_raise(self):
        validate_logo_file("image/png", MAX_LOGO_SIZE_BYTES)

    def test_allowed_content_type_over_max_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_logo_file("image/png", MAX_LOGO_SIZE_BYTES + 1)
        assert exc_info.value.status_code == 400
        assert "volumineux" in str(exc_info.value.detail).lower() or "maximale" in str(
            exc_info.value.detail
        ).lower()

    def test_all_allowed_mimetypes_accepted(self):
        for ct in ALLOWED_LOGO_MIMETYPES:
            validate_logo_file(ct, 0)
