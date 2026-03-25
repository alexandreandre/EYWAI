"""
Tests unitaires du domaine rates : règles métier (domain/rules.py).

Le module rates n'a pas d'entités ni de value objects (placeholders).
On teste : RATE_CATEGORY_OUTPUT_KEYS, group_and_select_best, build_rate_category_output.
Aucune I/O, aucune DB, aucun HTTP.
"""

from app.modules.rates.domain.rules import (
    RATE_CATEGORY_OUTPUT_KEYS,
    build_rate_category_output,
    group_and_select_best,
)


class TestRateCategoryOutputKeys:
    """Contrat des clés exposées pour une catégorie de taux (API legacy)."""

    def test_output_keys_defined(self):
        """Les clés de sortie sont fixées et incluent config_data, version, etc."""
        assert "config_data" in RATE_CATEGORY_OUTPUT_KEYS
        assert "version" in RATE_CATEGORY_OUTPUT_KEYS
        assert "last_checked_at" in RATE_CATEGORY_OUTPUT_KEYS
        assert "comment" in RATE_CATEGORY_OUTPUT_KEYS
        assert "source_links" in RATE_CATEGORY_OUTPUT_KEYS
        assert len(RATE_CATEGORY_OUTPUT_KEYS) == 5


class TestGroupAndSelectBest:
    """Regroupement par config_key et sélection de la meilleure ligne (version puis created_at)."""

    def test_empty_list_returns_empty_dict(self):
        """Liste vide → dict vide."""
        assert group_and_select_best([]) == {}

    def test_single_row_returned(self):
        """Une seule ligne est retournée telle quelle, indexée par config_key."""
        rows = [
            {
                "config_key": "cotisations_urssaf",
                "config_data": {"taux": 0.45},
                "version": 1,
                "created_at": "2025-01-15T10:00:00Z",
            }
        ]
        result = group_and_select_best(rows)
        assert list(result.keys()) == ["cotisations_urssaf"]
        assert result["cotisations_urssaf"]["version"] == 1
        assert result["cotisations_urssaf"]["config_data"] == {"taux": 0.45}

    def test_same_config_key_higher_version_wins(self):
        """Pour une même config_key, la ligne avec la version la plus haute est retenue."""
        rows = [
            {
                "config_key": "taux_cse",
                "version": 1,
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "config_key": "taux_cse",
                "version": 3,
                "created_at": "2025-01-01T00:00:00Z",
            },
            {
                "config_key": "taux_cse",
                "version": 2,
                "created_at": "2025-01-01T00:00:00Z",
            },
        ]
        result = group_and_select_best(rows)
        assert result["taux_cse"]["version"] == 3

    def test_same_config_key_same_version_most_recent_created_at_wins(self):
        """À version égale, la ligne avec created_at la plus récente est retenue."""
        rows = [
            {
                "config_key": "minimal_legal",
                "version": 2,
                "created_at": "2025-01-10T12:00:00Z",
            },
            {
                "config_key": "minimal_legal",
                "version": 2,
                "created_at": "2025-01-15T12:00:00Z",
            },
            {
                "config_key": "minimal_legal",
                "version": 2,
                "created_at": "2025-01-05T12:00:00Z",
            },
        ]
        result = group_and_select_best(rows)
        assert result["minimal_legal"]["created_at"] == "2025-01-15T12:00:00Z"

    def test_rows_without_config_key_skipped(self):
        """Les lignes sans config_key sont ignorées."""
        rows = [
            {"config_key": "valid_key", "version": 1},
            {"config_key": "", "version": 2},
            {"version": 1},
        ]
        result = group_and_select_best(rows)
        assert list(result.keys()) == ["valid_key"]
        assert result["valid_key"]["version"] == 1

    def test_multiple_config_keys_each_best_selected(self):
        """Plusieurs config_key : pour chacune, la meilleure ligne est retenue."""
        rows = [
            {"config_key": "A", "version": 1, "created_at": "2025-01-01T00:00:00Z"},
            {"config_key": "B", "version": 2, "created_at": "2025-01-01T00:00:00Z"},
            {"config_key": "A", "version": 2, "created_at": "2025-01-01T00:00:00Z"},
        ]
        result = group_and_select_best(rows)
        assert result["A"]["version"] == 2
        assert result["B"]["version"] == 2

    def test_none_version_treated_as_zero(self):
        """version None est traitée comme 0."""
        rows = [
            {"config_key": "x", "version": None, "created_at": "2025-01-01T00:00:00Z"},
            {"config_key": "x", "version": 1, "created_at": "2025-01-01T00:00:00Z"},
        ]
        result = group_and_select_best(rows)
        assert result["x"]["version"] == 1


class TestBuildRateCategoryOutput:
    """Construction du dict de sortie API (uniquement les clés RATE_CATEGORY_OUTPUT_KEYS)."""

    def test_extracts_only_output_keys(self):
        """Seules les clés du contrat sont présentes en sortie."""
        row = {
            "config_key": "ignored",
            "config_data": {"foo": "bar"},
            "version": 2,
            "last_checked_at": "2025-01-10T00:00:00Z",
            "comment": "Test",
            "source_links": ["https://example.com"],
            "created_at": "2025-01-01T00:00:00Z",
            "is_active": True,
        }
        out = build_rate_category_output(row)
        assert set(out.keys()) == set(RATE_CATEGORY_OUTPUT_KEYS)
        assert "config_key" not in out
        assert "created_at" not in out
        assert "is_active" not in out

    def test_missing_keys_present_with_none_or_absent(self):
        """Clés absentes de la row → présentes en sortie via .get() (None si non fourni)."""
        row = {"config_data": {"x": 1}}
        out = build_rate_category_output(row)
        assert out["config_data"] == {"x": 1}
        assert out.get("version") is None
        assert out.get("last_checked_at") is None
        assert out.get("comment") is None
        assert out.get("source_links") is None

    def test_empty_row_yields_dict_with_none_values(self):
        """Row vide → dict avec toutes les clés, valeurs None."""
        out = build_rate_category_output({})
        for k in RATE_CATEGORY_OUTPUT_KEYS:
            assert k in out
            assert out[k] is None
