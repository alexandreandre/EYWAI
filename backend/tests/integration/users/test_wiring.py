"""
Tests d'intégration du câblage (wiring) du module users.

Vérifie que l'injection des dépendances et le flux de bout en bout fonctionnent :
router monté, get_current_user → queries/commands → repositories.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user
from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration


def _fake_user():
    return User(
        id="wiring-user-1",
        email="wiring@example.com",
        first_name="Wiring",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id="c1",
                company_name="Société Wiring",
                role="admin",
                is_primary=True,
            )
        ],
        active_company_id="c1",
    )


class TestUsersModuleWiring:
    """Vérification que le module users est correctement branché."""

    def test_users_router_is_mounted(self):
        """Les routes /api/users/* existent (pas 404 Not Found sur une route valide sans auth)."""
        client = TestClient(app)
        response = client.get("/api/users/me")
        assert response.status_code == 401
        assert "api/users" in str(response.request.url) or response.status_code != 404

    def test_get_me_flow_with_dependency_override(self):
        """GET /api/users/me avec get_current_user surchargé : flux query → réponse 200."""
        override_user = _fake_user()

        def _override():
            return override_user

        app.dependency_overrides[get_current_user] = _override
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == override_user.id
            assert data["email"] == override_user.email
            assert data["first_name"] == override_user.first_name
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_get_my_companies_flow_with_dependency_override(self):
        """GET /api/users/my-companies avec get_current_user surchargé : flux query → liste."""
        override_user = _fake_user()

        def _override():
            return override_user

        app.dependency_overrides[get_current_user] = _override
        try:
            client = TestClient(app)
            response = client.get("/api/users/my-companies")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["company_id"] == "c1"
            assert data[0]["company_name"] == "Société Wiring"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.users.application.queries.infra_queries")
    def test_get_accessible_companies_uses_infra_queries_for_super_admin(
        self, infra_queries
    ):
        """Pour un super_admin, get_accessible_companies passe par infra_queries."""
        infra_queries.fetch_active_companies_for_creation.return_value = [
            {"id": "c1", "company_name": "Comp1"}
        ]
        super_user = User(
            id="sa-1",
            email="sa@example.com",
            first_name="Super",
            last_name="Admin",
            is_super_admin=True,
            is_group_admin=False,
            accessible_companies=[],
            active_company_id=None,
        )

        def _override():
            return super_user

        app.dependency_overrides[get_current_user] = _override
        try:
            client = TestClient(app)
            response = client.get("/api/users/accessible-companies")
            assert response.status_code == 200
            infra_queries.fetch_active_companies_for_creation.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
