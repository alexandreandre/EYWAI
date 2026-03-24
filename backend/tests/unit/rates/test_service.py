"""
Tests unitaires du service applicatif rates (application/service.py).

group_payroll_configs_by_key(rows) : groupement par config_key (règles domain) + formatage sortie.
Aucune I/O ; dépendances = règles du domain (pures).
"""
from app.modules.rates.application.service import group_payroll_configs_by_key


class TestGroupPayrollConfigsByKey:
    """Service : groupement et formatage des configs payroll."""

    def test_empty_rows_returns_empty_dict(self):
        """Liste vide → dict vide."""
        assert group_payroll_configs_by_key([]) == {}

    def test_single_row_formatted_with_output_keys_only(self):
        """Une ligne → une entrée, uniquement les clés de sortie API."""
        rows = [
            {
                "config_key": "minimal_legal",
                "config_data": {"smic": 1800},
                "version": 1,
                "last_checked_at": "2025-01-10T00:00:00Z",
                "comment": "SMIC",
                "source_links": [],
                "created_at": "2025-01-01T00:00:00Z",
                "is_active": True,
            }
        ]
        result = group_payroll_configs_by_key(rows)
        assert list(result.keys()) == ["minimal_legal"]
        out = result["minimal_legal"]
        assert out["config_data"] == {"smic": 1800}
        assert out["version"] == 1
        assert out["last_checked_at"] == "2025-01-10T00:00:00Z"
        assert out["comment"] == "SMIC"
        assert out["source_links"] == []
        assert "config_key" not in out
        assert "created_at" not in out
        assert "is_active" not in out

    def test_best_row_per_key_selected_by_version_then_created_at(self):
        """Pour une même config_key, version max puis created_at le plus récent."""
        rows = [
            {"config_key": "x", "version": 1, "config_data": {"v": 1}, "last_checked_at": None, "comment": None, "source_links": None, "created_at": "2025-01-01T00:00:00Z"},
            {"config_key": "x", "version": 2, "config_data": {"v": 2}, "last_checked_at": None, "comment": None, "source_links": None, "created_at": "2025-01-05T00:00:00Z"},
            {"config_key": "x", "version": 2, "config_data": {"v": "latest"}, "last_checked_at": None, "comment": None, "source_links": None, "created_at": "2025-01-10T00:00:00Z"},
        ]
        result = group_payroll_configs_by_key(rows)
        assert result["x"]["version"] == 2
        assert result["x"]["config_data"] == {"v": "latest"}
        assert result["x"]["last_checked_at"] is None

    def test_multiple_keys_each_with_best_row(self):
        """Plusieurs config_key : chacune a sa meilleure ligne."""
        rows = [
            {"config_key": "A", "version": 2, "config_data": {"a": 2}, "last_checked_at": None, "comment": None, "source_links": None},
            {"config_key": "B", "version": 1, "config_data": {"b": 1}, "last_checked_at": None, "comment": None, "source_links": None},
            {"config_key": "A", "version": 1, "config_data": {"a": 1}, "last_checked_at": None, "comment": None, "source_links": None},
        ]
        result = group_payroll_configs_by_key(rows)
        assert result["A"]["version"] == 2 and result["A"]["config_data"] == {"a": 2}
        assert result["B"]["version"] == 1 and result["B"]["config_data"] == {"b": 1}
