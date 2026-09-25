"""Endpoint de resynchro : réservé à l'environnement de test et aux super admins.

La resynchro remplace toute la base de test par la production. Depuis le
24/09/2026 cette base porte une vraie paie (Colorplast) : la déclencher n'est
plus un geste anodin, il faut être super administrateur.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import settings
from app.modules.super_admin.api.router import verify_super_admin


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def super_admin():
    from app.main import app

    app.dependency_overrides[verify_super_admin] = lambda: {"user_id": "sa-1"}
    yield
    app.dependency_overrides.pop(verify_super_admin, None)


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


def test_refresh_exige_une_authentification(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro"
    ) as declencher:
        r = client.post("/api/test-env/refresh")
    assert r.status_code in (401, 403)
    declencher.assert_not_called()


def test_refresh_refuse_en_production(client, super_admin, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro"
    ) as declencher:
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 403
    declencher.assert_not_called()


def test_refresh_declenche_le_workflow_en_environnement_de_test(
    client, super_admin, monkeypatch
):
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


def test_refresh_signale_une_configuration_manquante(client, super_admin, monkeypatch):
    from app.modules.test_env.domain.exceptions import RefreshNotConfigured

    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro",
        side_effect=RefreshNotConfigured("jeton absent"),
    ):
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 500
    assert "jeton absent" in r.json()["detail"]


def test_refresh_signale_un_refus_de_github(client, super_admin, monkeypatch):
    from app.modules.test_env.domain.exceptions import RefreshDispatchRefused

    monkeypatch.setattr(settings, "APP_ENV", "test")
    with patch(
        "app.modules.test_env.api.router.declencher_workflow_resynchro",
        side_effect=RefreshDispatchRefused("refusé"),
    ):
        r = client.post("/api/test-env/refresh")
    assert r.status_code == 502
