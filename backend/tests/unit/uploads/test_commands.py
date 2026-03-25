"""
Tests unitaires des commandes uploads (application/commands.py).

Repositories et storage mockés. Service (ensure_can_edit_entity_logo, validate_logo_file)
mocké pour isoler la logique des commandes.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.uploads.application import commands
from app.modules.uploads.application.dto import (
    DeleteLogoResult,
    LogoScaleResult,
    UploadLogoResult,
)
from app.modules.users.schemas.responses import User


def _make_user(
    user_id: str = "user-1",
    is_super_admin: bool = False,
) -> User:
    """Fabrique un User pour les tests."""
    return User(
        id=user_id,
        email="user@test.com",
        first_name="Test",
        last_name="User",
        is_super_admin=is_super_admin,
        accessible_companies=[],
        active_company_id="company-1",
    )


@patch("app.modules.uploads.application.commands.ensure_can_edit_entity_logo")
@patch("app.modules.uploads.application.commands.validate_logo_file")
@patch("app.modules.uploads.application.commands.storage")
@patch("app.modules.uploads.application.commands.repo")
class TestUploadLogo:
    """Commande upload_logo (async, exécutée via asyncio.run)."""

    def test_upload_logo_success(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_validate: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_validate.return_value = None
        mock_storage.get_logo_public_url.return_value = (
            "https://storage/logos/companies/company_1_uuid.png"
        )
        mock_repo.update_logo_url.return_value = True

        result = asyncio.run(
            commands.upload_logo(
                file_content=b"\x89PNG\r\n",
                content_type="image/png",
                filename="logo.png",
                entity_type="company",
                entity_id="company-1",
                current_user=_make_user(),
            )
        )

        assert isinstance(result, UploadLogoResult)
        assert result.logo_url == "https://storage/logos/companies/company_1_uuid.png"
        assert "succès" in result.message or "uploadé" in result.message
        mock_ensure.assert_called_once()
        mock_validate.assert_called_once_with("image/png", len(b"\x89PNG\r\n"))
        mock_storage.upload_logo_file.assert_called_once()
        mock_repo.update_logo_url.assert_called_once()

    def test_upload_logo_storage_error_raises_500(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_validate: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_validate.return_value = None
        mock_storage.upload_logo_file.side_effect = Exception("Storage error")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                commands.upload_logo(
                    file_content=b"x",
                    content_type="image/png",
                    filename="logo.png",
                    entity_type="company",
                    entity_id="company-1",
                    current_user=_make_user(),
                )
            )
        assert exc_info.value.status_code == 500
        assert "upload" in str(exc_info.value.detail).lower()

    def test_upload_logo_update_fails_removes_file_and_raises_404(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_validate: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_validate.return_value = None
        mock_storage.get_logo_public_url.return_value = "https://storage/path.png"
        mock_repo.update_logo_url.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                commands.upload_logo(
                    file_content=b"x",
                    content_type="image/png",
                    filename="logo.png",
                    entity_type="company",
                    entity_id="company-1",
                    current_user=_make_user(),
                )
            )
        assert exc_info.value.status_code == 404
        assert "trouvé" in str(exc_info.value.detail).lower()
        mock_storage.remove_logo_files.assert_called_once()


@patch("app.modules.uploads.application.commands.ensure_can_edit_entity_logo")
@patch("app.modules.uploads.application.commands.storage_path_from_logo_url")
@patch("app.modules.uploads.application.commands.storage")
@patch("app.modules.uploads.application.commands.repo")
class TestDeleteLogo:
    """Commande delete_logo."""

    def test_delete_logo_entity_not_found_raises_404(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_path_from_url: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_repo.entity_exists.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            commands.delete_logo(
                entity_type="company",
                entity_id="company-1",
                current_user=_make_user(),
            )
        assert exc_info.value.status_code == 404
        mock_repo.entity_exists.assert_called_once_with("company", "company-1")

    def test_delete_logo_no_logo_returns_message(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_path_from_url: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_repo.entity_exists.return_value = True
        mock_repo.get_logo_url.return_value = None

        result = commands.delete_logo(
            entity_type="company",
            entity_id="company-1",
            current_user=_make_user(),
        )

        assert isinstance(result, DeleteLogoResult)
        assert "Aucun logo" in result.message
        mock_repo.update_logo_url.assert_not_called()

    def test_delete_logo_success_removes_storage_and_updates_db(
        self,
        mock_repo: MagicMock,
        mock_storage: MagicMock,
        mock_path_from_url: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_repo.entity_exists.return_value = True
        mock_repo.get_logo_url.return_value = (
            "https://example.com/logos/logos/companies/logo.png"
        )
        mock_path_from_url.return_value = "logos/companies/logo.png"

        result = commands.delete_logo(
            entity_type="company",
            entity_id="company-1",
            current_user=_make_user(),
        )

        assert isinstance(result, DeleteLogoResult)
        assert "supprimé" in result.message
        mock_path_from_url.assert_called_once_with(
            "https://example.com/logos/logos/companies/logo.png"
        )
        mock_storage.remove_logo_files.assert_called_once_with(
            ["logos/companies/logo.png"]
        )
        mock_repo.update_logo_url.assert_called_once_with("company", "company-1", None)


@patch("app.modules.uploads.application.commands.ensure_can_edit_entity_logo")
@patch("app.modules.uploads.application.commands.repo")
class TestUpdateLogoScale:
    """Commande update_logo_scale."""

    def test_update_logo_scale_invalid_scale_raises_400(
        self,
        mock_repo: MagicMock,
        mock_ensure: MagicMock,
    ):
        with pytest.raises(HTTPException) as exc_info:
            commands.update_logo_scale(
                entity_type="company",
                entity_id="company-1",
                scale=0.1,
                current_user=_make_user(),
            )
        assert exc_info.value.status_code == 400
        assert "zoom" in str(exc_info.value.detail).lower() or "0.5" in str(
            exc_info.value.detail
        )
        mock_ensure.assert_not_called()

    def test_update_logo_scale_entity_not_found_raises_404(
        self,
        mock_repo: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_repo.update_logo_scale.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            commands.update_logo_scale(
                entity_type="company",
                entity_id="company-1",
                scale=1.0,
                current_user=_make_user(),
            )
        assert exc_info.value.status_code == 404
        mock_repo.update_logo_scale.assert_called_once_with("company", "company-1", 1.0)

    def test_update_logo_scale_success(
        self,
        mock_repo: MagicMock,
        mock_ensure: MagicMock,
    ):
        mock_ensure.return_value = None
        mock_repo.update_logo_scale.return_value = True

        result = commands.update_logo_scale(
            entity_type="company",
            entity_id="company-1",
            scale=1.5,
            current_user=_make_user(),
        )

        assert isinstance(result, LogoScaleResult)
        assert result.logo_scale == 1.5
        assert (
            "zoom" in result.message.lower() or "mis à jour" in result.message.lower()
        )
