"""
Tests d'intégration HTTP des routes du module companies.

Routes : GET /api/company/details, GET /api/company/settings, PATCH /api/company/settings.
Utilise : client (TestClient). Pour les routes protégées : dependency_overrides pour
get_current_user et mocks pour repository / fetch_company_with_employees_and_payslips
et get_company_id_from_profile (pas de JWT ni DB réels requis).

Fixture documentée : companies_headers — si besoin de tests E2E avec token réel,
ajouter dans conftest.py une fixture companies_headers (ou auth_headers) pour un
utilisateur avec active_company_id et droits RH pour PATCH /settings.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

# IDs de test pour entreprise et utilisateur
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_user_with_company(role: str = "admin", active_company_id: str = TEST_COMPANY_ID):
    """Utilisateur avec une entreprise active et un rôle donné."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role=role,
        is_primary=True,
    )
    user = User(
        id=TEST_USER_ID,
        email="user@test.com",
        first_name="Test",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=active_company_id,
    )
    return user


def _make_user_without_company():
    """Utilisateur sans entreprise active."""
    return User(
        id=TEST_USER_ID,
        email="user@test.com",
        first_name="Test",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


class TestCompanyDetails:
    """GET /api/company/details."""

    def test_details_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/company/details")
        assert response.status_code == 401

    def test_details_with_user_no_company_returns_403(self, client: TestClient):
        """Utilisateur sans company_id (profil) → 403."""
        from app.core.security import get_current_user
        user = _make_user_without_company()
        with patch(
            "app.modules.companies.infrastructure.queries.get_company_id_from_profile",
            return_value=None,
        ):
            app.dependency_overrides[get_current_user] = lambda: user
            try:
                response = client.get("/api/company/details")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "entreprise" in response.json().get("detail", "").lower()

    def test_details_with_mock_data_returns_200(self, client: TestClient):
        """Avec company_id résolu et données mockées → 200 et company_data + kpis."""
        from app.core.security import get_current_user
        user = _make_user_with_company()
        company_data = {"id": TEST_COMPANY_ID, "company_name": "Test SARL"}
        with patch(
            "app.modules.companies.infrastructure.queries.get_company_id_from_profile",
            return_value=TEST_COMPANY_ID,
        ), patch(
            "app.modules.companies.application.queries.fetch_company_with_employees_and_payslips",
            return_value={
                "company_data": company_data,
                "employees": [{"id": "e1", "contract_type": "CDI", "job_title": "Dev"}],
                "payslips": [],
            },
        ):
            app.dependency_overrides[get_current_user] = lambda: user
            try:
                response = client.get("/api/company/details")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["company_data"] == company_data
        assert "kpis" in data
        assert data["kpis"]["total_employees"] == 1


class TestCompanySettingsGet:
    """GET /api/company/settings."""

    def test_settings_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/company/settings")
        assert response.status_code == 401

    def test_settings_without_active_company_returns_400(self, client: TestClient):
        """Utilisateur sans entreprise active → 400."""
        from app.core.security import get_current_user
        user = _make_user_without_company()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.get("/api/company/settings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 400
        assert "entreprise" in response.json().get("detail", "").lower() or "active" in response.json().get("detail", "").lower()

    def test_settings_with_mock_repo_returns_200(self, client: TestClient):
        """Avec entreprise active et repository mocké → 200 et settings."""
        from app.core.security import get_current_user
        user = _make_user_with_company()
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": True}
        with patch(
            "app.modules.companies.application.queries.company_repository",
            mock_repo,
        ):
            app.dependency_overrides[get_current_user] = lambda: user
            try:
                response = client.get("/api/company/settings")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["medical_follow_up_enabled"] is True
        assert "settings" in data


class TestCompanySettingsPatch:
    """PATCH /api/company/settings."""

    def test_patch_settings_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.patch(
            "/api/company/settings",
            json={"medical_follow_up_enabled": True},
        )
        assert response.status_code == 401

    def test_patch_settings_without_active_company_returns_400(self, client: TestClient):
        """Sans entreprise active → 400."""
        from app.core.security import get_current_user
        user = _make_user_without_company()
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.patch(
                "/api/company/settings",
                json={"medical_follow_up_enabled": True},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 400

    def test_patch_settings_without_rh_access_returns_403(self, client: TestClient):
        """Utilisateur collaborateur (sans droits RH) → 403."""
        from app.core.security import get_current_user
        user = _make_user_with_company(role="collaborateur")
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.patch(
                "/api/company/settings",
                json={"medical_follow_up_enabled": True},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "Droits" in response.json().get("detail", "") or "insuffisants" in response.json().get("detail", "")

    def test_patch_settings_with_rh_user_and_mock_repo_returns_200(self, client: TestClient):
        """Utilisateur RH + repository mocké → 200 et settings mis à jour."""
        from app.core.security import get_current_user
        user = _make_user_with_company(role="rh")
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": False}
        mock_repo.update_settings.return_value = None
        with patch(
            "app.modules.companies.application.commands.company_repository",
            mock_repo,
        ):
            app.dependency_overrides[get_current_user] = lambda: user
            try:
                response = client.patch(
                    "/api/company/settings",
                    json={"medical_follow_up_enabled": True},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["medical_follow_up_enabled"] is True
        mock_repo.update_settings.assert_called_once()
