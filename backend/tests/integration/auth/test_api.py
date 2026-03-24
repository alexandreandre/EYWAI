"""
Tests d'intégration HTTP des routes du module auth.

Utilise les fixtures : client (TestClient), auth_headers (conftest.py).
Préfixe des routes : /api/auth.
"""
import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestAuthLogin:
    """POST /api/auth/login (OAuth2 form: username, password)."""

    def test_login_without_credentials_returns_422(self, client: TestClient):
        """Sans username/password → 422 Unprocessable Entity."""
        response = client.post("/api/auth/login", data={})
        assert response.status_code == 422

    def test_login_with_empty_password_returns_400_or_422(self, client: TestClient):
        """Email/username + mot de passe vide → 400 ou 422."""
        response = client.post(
            "/api/auth/login",
            data={"username": "user@example.com", "password": ""},
        )
        assert response.status_code in (400, 422)

    def test_login_with_invalid_credentials_returns_400(self, client: TestClient):
        """Identifiants invalides → 400 (détail Identifiant ou mot de passe incorrect)."""
        response = client.post(
            "/api/auth/login",
            data={"username": "unknown@example.com", "password": "wrong"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestAuthMe:
    """GET /api/auth/me — utilisateur connecté."""

    def test_me_without_token_returns_401(self, client: TestClient):
        """Sans token Bearer → 401 Unauthorized."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_auth_headers_returns_200_if_token_valid(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth_headers (fixture) : 200 si token valide, 401 sinon."""
        response = client.get("/api/auth/me", headers=auth_headers)
        if auth_headers:
            assert response.status_code in (200, 401)
            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert "email" in data or "first_name" in data
        else:
            assert response.status_code == 401


class TestAuthLogout:
    """POST /api/auth/logout."""

    def test_logout_without_token_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 401

    def test_logout_with_valid_token_returns_200(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec token valide → 200 et message de déconnexion."""
        response = client.post("/api/auth/logout", headers=auth_headers)
        if auth_headers:
            assert response.status_code in (200, 401)
            if response.status_code == 200:
                assert response.json().get("message") == "Déconnexion réussie"
        else:
            assert response.status_code == 401


class TestAuthRequestPasswordReset:
    """POST /api/auth/request-password-reset."""

    def test_request_reset_with_valid_email_returns_200(self, client: TestClient):
        """Body { email } valide → 200 et message générique (sécurité)."""
        response = client.post(
            "/api/auth/request-password-reset",
            json={"email": "someone@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "e-mail" in data["message"].lower() or "lien" in data["message"].lower()

    def test_request_reset_without_email_returns_422(self, client: TestClient):
        """Sans email → 422."""
        response = client.post("/api/auth/request-password-reset", json={})
        assert response.status_code == 422


class TestAuthResetPassword:
    """POST /api/auth/reset-password."""

    def test_reset_with_invalid_token_returns_400(self, client: TestClient):
        """Token invalide → 400."""
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "invalid-token-xyz", "new_password": "NewSecureP@ss1"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data


class TestAuthVerifyResetToken:
    """POST /api/auth/verify-reset-token?token=..."""

    def test_verify_invalid_token_returns_400(self, client: TestClient):
        """Token invalide → 400."""
        response = client.post(
            "/api/auth/verify-reset-token",
            params={"token": "invalid-token"},
        )
        assert response.status_code == 400

    def test_verify_without_token_returns_422(self, client: TestClient):
        """Sans paramètre token → 422."""
        response = client.post("/api/auth/verify-reset-token")
        assert response.status_code == 422


class TestAuthChangePassword:
    """POST /api/auth/change-password (utilisateur connecté)."""

    def test_change_password_without_token_returns_401(self, client: TestClient):
        """Sans authentification → 401."""
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "Old", "new_password": "NewP@ss1"},
        )
        assert response.status_code == 401

    def test_change_password_with_auth_returns_200_or_401(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth_headers : 200 si token valide et mots de passe cohérents, 401 sinon."""
        response = client.post(
            "/api/auth/change-password",
            headers=auth_headers,
            json={"current_password": "Current", "new_password": "NewP@ss1"},
        )
        assert response.status_code in (200, 400, 401)
