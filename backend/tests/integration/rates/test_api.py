"""
Tests d'intégration HTTP des routes du module rates.

Route : GET /api/rates/all (récupération des configs actives de taux, groupées par config_key).
Utilise : client (TestClient), dependency_overrides pour get_all_rates_reader et get_current_user.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.rates.api.dependencies import get_all_rates_reader


pytestmark = pytest.mark.integration


def _make_mock_reader(rows):
    """Reader mocké qui retourne les lignes fournies."""
    reader = MagicMock()
    reader.get_all_active_rows.return_value = rows
    return reader


def _make_rh_user():
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company = lambda _cid: True
    return user


def _make_non_rh_user():
    user = MagicMock()
    user.is_platform_admin = False
    user.active_company_id = "company-1"
    user.has_rh_access_in_company = lambda _cid: False
    return user


class TestGetAllRatesEndpoint:
    """GET /api/rates/all."""

    def test_returns_200_with_rates_when_data_exists(self, client: TestClient):
        """Quand le reader retourne des lignes, réponse 200 et dict groupé par config_key."""
        rows = [
            {
                "config_key": "cotisations_urssaf",
                "config_data": {"taux": 0.45},
                "version": 1,
                "last_checked_at": "2025-01-10T00:00:00Z",
                "comment": "URSSAF",
                "source_links": ["https://urssaf.fr"],
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
        mock_reader = _make_mock_reader(rows)
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "cotisations_urssaf" in data
        out = data["cotisations_urssaf"]
        assert out["config_data"] == {"taux": 0.45}
        assert out["version"] == 1
        assert out["comment"] == "URSSAF"
        mock_reader.get_all_active_rows.assert_called_once()

    def test_returns_404_when_no_active_config(self, client: TestClient):
        """Quand le reader retourne une liste vide, le routeur renvoie 404."""
        mock_reader = _make_mock_reader([])
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 404
        assert "Aucune configuration active" in response.json().get("detail", "")

    def test_returns_500_when_reader_raises(self, client: TestClient):
        """Quand le reader lève une exception, le routeur renvoie 500."""
        mock_reader = MagicMock()
        mock_reader.get_all_active_rows.side_effect = RuntimeError("DB unreachable")
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 500
        assert "DB unreachable" in response.json().get("detail", "")

    def test_response_structure_matches_rate_category_output_keys(
        self, client: TestClient
    ):
        """Chaque entrée du dict contient uniquement les clés de sortie (config_data, version, etc.)."""
        rows = [
            {
                "config_key": "minimal_legal",
                "config_data": {"smic": 1800},
                "version": 2,
                "last_checked_at": "2025-01-15T00:00:00Z",
                "comment": "SMIC",
                "source_links": [],
                "created_at": "2025-01-01T00:00:00Z",
                "is_active": True,
            }
        ]
        mock_reader = _make_mock_reader(rows)
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        out = response.json()["minimal_legal"]
        assert set(out.keys()) == {
            "config_data",
            "version",
            "last_checked_at",
            "comment",
            "source_links",
        }
        assert "config_key" not in out
        assert "created_at" not in out
        assert "is_active" not in out

    def test_returns_401_without_authentication(self, client: TestClient):
        """Sans get_current_user injecté ni token, l'endpoint est protégé (401)."""
        response = client.get("/api/rates/all")
        assert response.status_code == 401

    def test_returns_403_for_non_rh_user(self, client: TestClient):
        """Un utilisateur sans accès RH sur la company active reçoit 403."""
        mock_reader = _make_mock_reader([])
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        app.dependency_overrides[get_current_user] = _make_non_rh_user
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403
        assert "rh" in response.json().get("detail", "").lower()


class TestRatesSyncEndpoints:
    """POST /api/rates/sync et GET /api/rates/sync/{sync_id}/status."""

    @patch("app.modules.rates.api.router.start_rates_sync")
    def test_post_sync_returns_batch(self, mock_start, client: TestClient):
        mock_start.return_value = {
            "sync_id": "sync-abc",
            "jobs": [{"source_key": "smic", "job_id": "j1", "status": "running"}],
            "total": 1,
            "message": "ok",
        }
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.post("/api/rates/sync")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["sync_id"] == "sync-abc"

    @patch("app.modules.rates.api.router.start_rates_sync")
    def test_post_sync_with_rate_keys(self, mock_start, client: TestClient):
        mock_start.return_value = {"sync_id": "s1", "jobs": [], "total": 0, "message": "ok"}
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.post("/api/rates/sync", json={"rate_keys": ["smic"]})
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_start.assert_called_once()
        assert mock_start.call_args.kwargs.get("rate_keys") == ["smic"]

    @patch("app.modules.rates.api.router.get_rates_sync_sources_manifest")
    def test_get_sync_sources(self, mock_manifest, client: TestClient):
        mock_manifest.return_value = {"rate_categories": [], "all_critical_count": 0}
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/sync/sources")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200

    @patch("app.modules.rates.api.router.get_rates_sync_status")
    def test_get_sync_status(self, mock_status, client: TestClient):
        mock_status.return_value = {
            "sync_id": "sync-abc",
            "status": "running",
            "progress": {"total": 1, "running": 1, "completed": 0, "failed": 0, "done": 0, "percent": 0},
            "jobs": [],
            "created_at": "2025-01-01T00:00:00Z",
        }
        app.dependency_overrides[get_current_user] = _make_rh_user
        try:
            response = client.get("/api/rates/sync/sync-abc/status")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_post_sync_403_non_rh(self, client: TestClient):
        app.dependency_overrides[get_current_user] = _make_non_rh_user
        try:
            response = client.post("/api/rates/sync")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403
