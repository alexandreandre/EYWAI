"""
Smoke tests globaux : démarrage app, health, openapi, auth login/me.

Regroupe test_startup_health (app starts, health endpoint, openapi) et des
smoke auth. Utilise les fixtures client et auth_headers du conftest.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app


pytestmark = pytest.mark.e2e


# --- test_startup_health (regroupé ici) ---


def test_app_starts():
    """Import de app depuis app.main ne lève pas d'exception ; l'objet app est créé."""
    assert app is not None
    assert isinstance(app, FastAPI)


def test_app_imports():
    """Importer app depuis app.main et vérifier que app est une instance FastAPI."""
    assert app is not None
    assert isinstance(app, FastAPI)


def test_health_endpoint(client: TestClient):
    """GET /health retourne 200 et un JSON avec status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_health(client: TestClient):
    """GET /health : status 200 et body contenant {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_openapi_available(client: TestClient):
    """GET /openapi.json retourne 200 pour confirmer que l'app répond."""
    response = client.get("/openapi.json")
    assert response.status_code == 200


# --- auth smoke (détails dans test_auth_flow.py) ---


def test_auth_login(client: TestClient):
    """POST /api/auth/login avec payload minimal ; accepter 200 (succès) ou 401 (bad credentials), pas 500."""
    response = client.post(
        "/api/auth/login",
        data={"username": "smoke@test.local", "password": "smoke-password"},
    )
    assert response.status_code in (200, 400, 401), (
        f"Login doit retourner 200, 400 ou 401, pas {response.status_code}"
    )
    assert response.status_code != 500


def test_auth_me(client: TestClient, auth_headers: dict):
    """GET /api/auth/me avec auth_headers ; accepter 200 ou 401, pas 500."""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code in (200, 401), (
        f"/api/auth/me doit retourner 200 ou 401, pas {response.status_code}"
    )
    assert response.status_code != 500
