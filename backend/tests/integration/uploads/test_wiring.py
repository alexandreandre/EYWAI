"""
Tests de wiring (injection de dépendances et flux bout en bout) pour le module uploads.

Vérifie que le router appelle bien les commandes, que les commandes utilisent
storage/repository/service, et que les réponses HTTP correspondent aux DTOs.
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.uploads.application.commands import (
    delete_logo,
    update_logo_scale,
)
from app.modules.uploads.application.dto import DeleteLogoResult, LogoScaleResult
from app.modules.users.schemas.responses import User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_user():
    return User(
        id=TEST_USER_ID,
        email="wiring@test.com",
        first_name="Wiring",
        last_name="User",
        is_super_admin=True,
        accessible_companies=[],
        active_company_id=TEST_COMPANY_ID,
    )


class TestWiringRouterToCommands:
    """Le router délègue aux commandes et retourne les schémas de réponse."""

    def test_delete_logo_flow_returns_delete_response(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.repo") as mock_repo, patch(
            "app.modules.uploads.application.commands.storage"
        ) as mock_storage:
            mock_repo.entity_exists.return_value = True
            mock_repo.get_logo_url.return_value = None
            app.dependency_overrides[get_current_user] = _make_user
            try:
                response = client.delete(
                    f"/api/uploads/logo/company/{TEST_COMPANY_ID}",
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "message" in body

    def test_patch_logo_scale_flow_returns_scale_response(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.repo") as mock_repo:
            mock_repo.update_logo_scale.return_value = True
            app.dependency_overrides[get_current_user] = _make_user
            try:
                response = client.patch(
                    f"/api/uploads/logo-scale/company/{TEST_COMPANY_ID}",
                    params={"scale": 1.25},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["logo_scale"] == 1.25


class TestWiringCommandsReturnDtos:
    """Les commandes retournent bien les DTOs attendus (utilisés par le router)."""

    def test_delete_logo_returns_delete_result(self):
        with patch(
            "app.modules.uploads.application.commands.ensure_can_edit_entity_logo"
        ), patch("app.modules.uploads.application.commands.repo") as mock_repo:
            mock_repo.entity_exists.return_value = True
            mock_repo.get_logo_url.return_value = None

            result = delete_logo(
                entity_type="company",
                entity_id=TEST_COMPANY_ID,
                current_user=_make_user(),
            )
            assert isinstance(result, DeleteLogoResult)
            assert hasattr(result, "message")

    def test_update_logo_scale_returns_scale_result(self):
        with patch(
            "app.modules.uploads.application.commands.ensure_can_edit_entity_logo"
        ), patch("app.modules.uploads.application.commands.repo") as mock_repo:
            mock_repo.update_logo_scale.return_value = True

            result = update_logo_scale(
                entity_type="company",
                entity_id=TEST_COMPANY_ID,
                scale=1.5,
                current_user=_make_user(),
            )
            assert isinstance(result, LogoScaleResult)
            assert result.logo_scale == 1.5


class TestWiringInfrastructureInjected:
    """Les commandes utilisent bien l'infrastructure (repo, storage) injectée par le module."""

    def test_upload_logo_calls_storage_and_repo(self):
        from app.modules.uploads.application import commands

        with patch(
            "app.modules.uploads.application.commands.ensure_can_edit_entity_logo"
        ), patch(
            "app.modules.uploads.application.commands.validate_logo_file"
        ), patch(
            "app.modules.uploads.application.commands.storage"
        ) as mock_storage, patch(
            "app.modules.uploads.application.commands.repo"
        ) as mock_repo:
            mock_storage.get_logo_public_url.return_value = "https://url/logo.png"
            mock_repo.update_logo_url.return_value = True

            result = asyncio.run(commands.upload_logo(
                file_content=b"\x89PNG",
                content_type="image/png",
                filename="logo.png",
                entity_type="company",
                entity_id=TEST_COMPANY_ID,
                current_user=_make_user(),
            ))
            mock_storage.upload_logo_file.assert_called_once()
            mock_repo.update_logo_url.assert_called_once()
            assert result.logo_url == "https://url/logo.png"
