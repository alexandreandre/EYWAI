"""
Tests de câblage (wiring) du module rates : injection des dépendances et flux bout en bout.

Vérifie que :
- get_all_rates_reader est bien utilisé par le routeur et retourne un IAllRatesReader.
- Le flux reader → get_all_rates (query) → group_payroll_configs_by_key (service) → domain rules
  produit le résultat attendu sans erreur.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.rates.api.dependencies import get_all_rates_reader
from app.modules.rates.domain.interfaces import IAllRatesReader
from app.modules.rates.application.queries import get_all_rates


pytestmark = pytest.mark.integration


class TestRatesDependencyInjection:
    """Injection de get_all_rates_reader dans le routeur."""

    def test_get_all_rates_reader_returns_reader_interface(self):
        """get_all_rates_reader() retourne un objet avec get_all_active_rows (IAllRatesReader)."""
        reader = get_all_rates_reader()
        assert hasattr(reader, "get_all_active_rows")
        assert callable(getattr(reader, "get_all_active_rows"))

    def test_endpoint_uses_injected_reader(self, client: TestClient):
        """GET /api/rates/all utilise le reader injecté (override) et appelle get_all_active_rows."""
        mock_reader = MagicMock(spec=IAllRatesReader)
        mock_reader.get_all_active_rows.return_value = [
            {
                "config_key": "wiring_test",
                "config_data": {"ok": True},
                "version": 1,
                "last_checked_at": None,
                "comment": None,
                "source_links": None,
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

        assert response.status_code == 200
        mock_reader.get_all_active_rows.assert_called_once()
        data = response.json()
        assert "wiring_test" in data
        assert data["wiring_test"]["config_data"] == {"ok": True}


class TestRatesEndToEndFlow:
    """Flux complet : reader → query → service → domain → réponse HTTP."""

    def test_full_flow_with_mock_reader_produces_formatted_output(
        self, client: TestClient
    ):
        """De la lecture (mock) à la réponse JSON : format de sortie correct (clés API)."""
        rows = [
            {
                "config_key": "cotisations",
                "config_data": {"taux": 0.25},
                "version": 2,
                "last_checked_at": "2025-01-10T00:00:00Z",
                "comment": "Test",
                "source_links": ["https://example.com"],
                "created_at": "2025-01-05T00:00:00Z",
            }
        ]
        mock_reader = MagicMock()
        mock_reader.get_all_active_rows.return_value = rows
        app.dependency_overrides[get_all_rates_reader] = lambda: mock_reader
        try:
            response = client.get("/api/rates/all")
        finally:
            app.dependency_overrides.pop(get_all_rates_reader, None)

        assert response.status_code == 200
        body = response.json()
        assert "cotisations" in body
        out = body["cotisations"]
        assert out["config_data"] == {"taux": 0.25}
        assert out["version"] == 2
        assert out["last_checked_at"] == "2025-01-10T00:00:00Z"
        assert out["comment"] == "Test"
        assert out["source_links"] == ["https://example.com"]
        # Pas de fuite de champs internes
        assert "config_key" not in out
        assert "created_at" not in out

    def test_query_get_all_rates_uses_reader_and_returns_grouped_dict(self):
        """get_all_rates(reader) appelle le reader et retourne le dict groupé (sans passer par HTTP)."""
        mock_reader = MagicMock()
        mock_reader.get_all_active_rows.return_value = [
            {
                "config_key": "k1",
                "config_data": {},
                "version": 1,
                "last_checked_at": None,
                "comment": None,
                "source_links": None,
            },
        ]
        result = get_all_rates(mock_reader)
        mock_reader.get_all_active_rows.assert_called_once()
        assert result == {
            "k1": {
                "config_data": {},
                "version": 1,
                "last_checked_at": None,
                "comment": None,
                "source_links": None,
            }
        }
