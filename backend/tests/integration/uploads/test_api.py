"""
Tests d'intégration HTTP des routes du module uploads.

Routes : POST /api/uploads/logo, DELETE /api/uploads/logo/{entity_type}/{entity_id},
PATCH /api/uploads/logo-scale/{entity_type}/{entity_id}?scale=...
Utilise : client (TestClient), dependency_overrides pour get_current_user,
mocks storage et repository pour éviter DB et bucket réels.

Fixture optionnelle : uploads_headers (conftest.py) — en-têtes pour un utilisateur
authentifié avec droits sur une company/group pour les uploads. Si absente, les tests
utilisent dependency_overrides pour injecter un User de test.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"

# En-tête minimal pour que OAuth2PasswordBearer ne lève pas avant get_current_user.
# get_current_user est overridé par dependency_overrides, donc le token n'est pas validé.
AUTH_HEADERS = {"Authorization": "Bearer fake-token-for-test"}


def _make_rh_user(company_id: str = TEST_COMPANY_ID):
    """Utilisateur de test avec droits (admin/rh) sur l'entreprise."""
    return User(
        id=TEST_USER_ID,
        email="rh@uploads-test.com",
        first_name="RH",
        last_name="Uploads",
        is_super_admin=False,
        accessible_companies=[],
        active_company_id=company_id,
    )


def _make_super_admin():
    """Utilisateur super admin (peut modifier company et group)."""
    return User(
        id=TEST_USER_ID,
        email="admin@uploads-test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        accessible_companies=[],
        active_company_id=TEST_COMPANY_ID,
    )


class TestUploadsUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_post_logo_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/uploads/logo",
            data={"entity_type": "company", "entity_id": TEST_COMPANY_ID},
            files={"file": ("logo.png", b"\x89PNG\r\n", "image/png")},
        )
        assert response.status_code == 401

    def test_delete_logo_returns_401_without_auth(self, client: TestClient):
        response = client.delete(
            f"/api/uploads/logo/company/{TEST_COMPANY_ID}",
        )
        assert response.status_code == 401

    def test_patch_logo_scale_returns_401_without_auth(self, client: TestClient):
        response = client.patch(
            f"/api/uploads/logo-scale/company/{TEST_COMPANY_ID}",
            params={"scale": 1.0},
        )
        assert response.status_code == 401


class TestUploadLogoRoute:
    """POST /api/uploads/logo."""

    def test_upload_logo_with_auth_and_mocks_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.storage") as mock_storage, patch(
            "app.modules.uploads.application.commands.repo"
        ) as mock_repo, patch(
            "app.modules.uploads.application.service.infra_queries.can_edit_entity_logo",
            return_value=True,
        ):
            mock_storage.get_logo_public_url.return_value = (
                "https://storage.example.com/logos/companies/logo.png"
            )
            mock_repo.update_logo_url.return_value = True

            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/uploads/logo",
                    data={"entity_type": "company", "entity_id": TEST_COMPANY_ID},
                    files={"file": ("logo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
                    headers=AUTH_HEADERS,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "logo_url" in data
        assert data["logo_url"] == "https://storage.example.com/logos/companies/logo.png"

    def test_upload_logo_forbidden_without_rights_returns_403(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.uploads.application.service.infra_queries.can_edit_entity_logo"
        ) as mock_can:
            mock_can.return_value = False
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/uploads/logo",
                    data={"entity_type": "company", "entity_id": TEST_COMPANY_ID},
                    files={"file": ("logo.png", b"\x89PNG", "image/png")},
                    headers=AUTH_HEADERS,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403


class TestDeleteLogoRoute:
    """DELETE /api/uploads/logo/{entity_type}/{entity_id}."""

    def test_delete_logo_with_auth_and_mocks_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.repo") as mock_repo, patch(
            "app.modules.uploads.application.commands.storage"
        ) as mock_storage, patch(
            "app.modules.uploads.application.service.infra_queries.can_edit_entity_logo",
            return_value=True,
        ):
            mock_repo.entity_exists.return_value = True
            mock_repo.get_logo_url.return_value = (
                "https://example.com/storage/v1/logos/logos/companies/logo.png"
            )
            mock_repo.update_logo_url.return_value = True

            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.delete(
                    f"/api/uploads/logo/company/{TEST_COMPANY_ID}",
                    headers=AUTH_HEADERS,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "message" in data

    def test_delete_logo_entity_not_found_returns_404(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.repo") as mock_repo, patch(
            "app.modules.uploads.application.service.infra_queries.can_edit_entity_logo",
            return_value=True,
        ):
            mock_repo.entity_exists.return_value = False

            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.delete(
                    f"/api/uploads/logo/company/{TEST_COMPANY_ID}",
                    headers=AUTH_HEADERS,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404


class TestPatchLogoScaleRoute:
    """PATCH /api/uploads/logo-scale/{entity_type}/{entity_id}?scale=..."""

    def test_patch_logo_scale_with_auth_and_mocks_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.uploads.application.commands.repo") as mock_repo, patch(
            "app.modules.uploads.application.service.infra_queries.can_edit_entity_logo",
            return_value=True,
        ):
            mock_repo.update_logo_scale.return_value = True

            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.patch(
                    f"/api/uploads/logo-scale/company/{TEST_COMPANY_ID}",
                    params={"scale": 1.5},
                    headers=AUTH_HEADERS,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert data.get("logo_scale") == 1.5

    def test_patch_logo_scale_invalid_scale_returns_400(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.patch(
                f"/api/uploads/logo-scale/company/{TEST_COMPANY_ID}",
                params={"scale": 3.0},
                headers=AUTH_HEADERS,
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 422 or response.status_code == 400
