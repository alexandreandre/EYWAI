"""
Tests de câblage (wiring) du module auth : injection des dépendances et flux bout en bout.

Vérifie que le router auth est monté, que les routes répondent (pas 404),
et qu'un enchaînement typique (ex. request-password-reset → verify-reset-token) est cohérent.
"""
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestAuthRouterMounted:
    """Vérification que le router auth est bien inclus dans l'app."""

    def test_auth_prefix_responds_not_404(self, client: TestClient):
        """Les routes sous /api/auth répondent (401, 422, 400) et non 404."""
        response = client.get("/api/auth/me")
        assert response.status_code != 404

    def test_login_route_exists(self, client: TestClient):
        """POST /api/auth/login existe (422 si body manquant, pas 404)."""
        response = client.post("/api/auth/login")
        assert response.status_code != 404

    def test_request_password_reset_route_exists(self, client: TestClient):
        """POST /api/auth/request-password-reset existe."""
        response = client.post(
            "/api/auth/request-password-reset",
            json={"email": "test@example.com"},
        )
        assert response.status_code != 404
        assert response.status_code == 200

    def test_verify_reset_token_route_exists(self, client: TestClient):
        """POST /api/auth/verify-reset-token existe."""
        response = client.post(
            "/api/auth/verify-reset-token",
            params={"token": "dummy-token"},
        )
        assert response.status_code != 404


class TestAuthFlowE2E:
    """Flux de bout en bout (sans credentials réels)."""

    def test_request_reset_then_verify_invalid_token_flow(self, client: TestClient):
        """Demande reset → 200 ; vérification token invalide → 400. Enchaînement cohérent."""
        # Étape 1 : demande de réinitialisation (toujours 200 pour sécurité)
        r1 = client.post(
            "/api/auth/request-password-reset",
            json={"email": "nonexistent@example.com"},
        )
        assert r1.status_code == 200
        assert "message" in r1.json()

        # Étape 2 : vérification d'un token invalide
        r2 = client.post(
            "/api/auth/verify-reset-token",
            params={"token": "invalid-token-123"},
        )
        assert r2.status_code == 400
        assert "detail" in r2.json()

    def test_me_requires_auth(self, client: TestClient):
        """GET /api/auth/me sans token retourne 401 (auth bien requise)."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_change_password_requires_auth(self, client: TestClient):
        """POST /api/auth/change-password sans token retourne 401."""
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "old", "new_password": "NewP@ss1"},
        )
        assert response.status_code == 401
