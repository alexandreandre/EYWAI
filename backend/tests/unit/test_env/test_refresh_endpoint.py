"""Endpoint de resynchro : réservé à l'environnement de test."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import settings


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def test_status_indique_prod_par_defaut(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    r = client.get("/api/test-env/status")
    assert r.status_code == 200
    assert r.json() == {"is_test": False, "last_refresh_at": None}


def test_status_indique_test_quand_app_env_test(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.lire_derniere_resynchro", return_value=None
    ):
        r = client.get("/api/test-env/status")
    assert r.status_code == 200
    assert r.json()["is_test"] is True


def test_refresh_refuse_en_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro"
    ) as declencher:
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 403
    declencher.assert_not_called()


def test_refresh_declenche_le_workflow_en_environnement_de_test(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "EMAIL_FORCE_REDIRECT_TO", "test@eywai.fr")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro",
        return_value=True,
    ) as declencher:
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 200
    assert r.json() == {"triggered": True}
    declencher.assert_called_once()


def test_refresh_signale_une_configuration_manquante(client, monkeypatch):
    from app.modules.test_env.domain.exceptions import RefreshNotConfigured

    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro",
        side_effect=RefreshNotConfigured("jeton absent"),
    ):
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 500
    assert "jeton absent" in r.json()["detail"]


def test_refresh_signale_un_refus_de_github(client, monkeypatch):
    from app.modules.test_env.domain.exceptions import RefreshDispatchRefused

    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro",
        side_effect=RefreshDispatchRefused("refusé"),
    ):
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 502
