"""
Tests d'intégration HTTP des routes du module rates.

Route : GET /api/rates/all (récupération des configs actives de taux, groupées par config_key).
Utilise : client (TestClient), dependency_overrides pour get_all_rates_reader pour éviter la DB réelle.
Pas d'auth sur cette route (pas de get_current_user).
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.rates.api.dependencies import get_all_rates_reader


pytestmark = pytest.mark.integration


def _make_mock_reader(rows):
    """Reader mocké qui retourne les lignes fournies."""
    reader = MagicMock()
    reader.get_all_active_rows.return_value = rows
    return reader


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
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

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
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

        assert response.status_code == 404
        assert "Aucune configuration active" in response.json().get("detail", "")

    def test_returns_500_when_reader_raises(self, client: TestClient):
        """Quand le reader lève une exception, le routeur renvoie 500."""
        mock_reader = MagicMock()
        mock_reader.get_all_active_rows.side_effect = RuntimeError("DB unreachable")
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

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
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

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
