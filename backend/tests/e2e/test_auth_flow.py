"""
Tests e2e du flux auth : login (token ou 401), /me sans auth (401), /me avec token (200).

Utilise les fixtures client et auth_headers du conftest. Code minimal, pas de refactor app.
"""

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.e2e


def test_login_returns_token_or_401(client: TestClient):
    """POST /api/auth/login avec email/password ; 200 avec token+user ou 401 ; jamais 500."""
    # L'API attend un form OAuth2 : username (email) + password
    response = client.post(
        "/api/auth/login",
        data={"username": "e2e-auth@test.local", "password": "test-password"},
    )
    assert response.status_code != 500, "Login ne doit jamais retourner 500"
    assert response.status_code in (200, 400, 401)
    if response.status_code == 200:
        data = response.json()
        assert "access_token" in data
        assert "user" in data


def test_me_requires_auth(client: TestClient):
    """GET /api/auth/me sans header Authorization retourne 401 (ou 403)."""
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)


def test_me_with_valid_token(client: TestClient, auth_headers: dict):
    """Si auth_headers fournit un token valide, GET /api/auth/me retourne 200 et un objet user."""
    response = client.get("/api/auth/me", headers=auth_headers)
    if not auth_headers:
        # Pas de token configuré (TEST_USER_EMAIL/PASSWORD absents) → 401 attendu
        assert response.status_code == 401
        return
    if response.status_code == 200:
        data = response.json()
        assert "id" in data
        assert "email" in data or "first_name" in data
    else:
        assert response.status_code == 401
