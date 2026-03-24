"""
Tests unitaires des queries du module rates (application/queries.py).

get_all_rates(reader) : récupère les lignes via le reader, applique le service (groupement + formatage).
Reader mocké, pas de DB.
"""
from unittest.mock import MagicMock

import pytest

from app.modules.rates.application.queries import get_all_rates


class TestGetAllRates:
    """Query get_all_rates : délégation au reader puis groupement/formatage."""

    def test_returns_empty_dict_when_reader_returns_empty(self):
        """Reader sans lignes → dict vide."""
        reader = MagicMock()
        reader.get_all_active_rows.return_value = []
        result = get_all_rates(reader)
        assert result == {}
        reader.get_all_active_rows.assert_called_once()

    def test_returns_grouped_and_formatted_when_reader_returns_rows(self):
        """Reader avec lignes → dict groupé par config_key, format sortie (clés API)."""
        reader = MagicMock()
        reader.get_all_active_rows.return_value = [
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
        result = get_all_rates(reader)
        assert "cotisations_urssaf" in result
        out = result["cotisations_urssaf"]
        assert out["config_data"] == {"taux": 0.45}
        assert out["version"] == 1
        assert out["last_checked_at"] == "2025-01-10T00:00:00Z"
        assert out["comment"] == "URSSAF"
        assert out["source_links"] == ["https://urssaf.fr"]
        assert "config_key" not in out
        assert "created_at" not in out
        reader.get_all_active_rows.assert_called_once()

    def test_selects_best_row_per_config_key(self):
        """Plusieurs lignes pour une même config_key : la meilleure (version puis created_at) est retenue."""
        reader = MagicMock()
        reader.get_all_active_rows.return_value = [
            {"config_key": "taux_cse", "version": 1, "config_data": {}, "last_checked_at": None, "comment": None, "source_links": None, "created_at": "2025-01-01T00:00:00Z"},
            {"config_key": "taux_cse", "version": 2, "config_data": {"seuil": 20}, "last_checked_at": None, "comment": None, "source_links": None, "created_at": "2025-01-15T00:00:00Z"},
        ]
        result = get_all_rates(reader)
        assert list(result.keys()) == ["taux_cse"]
        assert result["taux_cse"]["version"] == 2
        assert result["taux_cse"]["config_data"] == {"seuil": 20}

    def test_multiple_config_keys_all_present(self):
        """Plusieurs config_key → toutes présentes en sortie."""
        reader = MagicMock()
        reader.get_all_active_rows.return_value = [
            {"config_key": "A", "config_data": {}, "version": 1, "last_checked_at": None, "comment": None, "source_links": None},
            {"config_key": "B", "config_data": {}, "version": 1, "last_checked_at": None, "comment": None, "source_links": None},
        ]
        result = get_all_rates(reader)
        assert set(result.keys()) == {"A", "B"}
        reader.get_all_active_rows.assert_called_once()
