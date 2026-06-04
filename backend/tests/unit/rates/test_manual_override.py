"""
Tests unitaires de la saisie manuelle des taux (module rates).

- application.manual.apply_manual_rate_override : validation + délégation au writer.
- infrastructure.repository.SupabaseRatesWriter.save_manual_version : versioning
  immuable (création v1, incrément de version, no-op si identique).

Hermétique : aucun accès DB réel, le client Supabase est mocké.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.rates.application.manual import apply_manual_rate_override
from app.modules.rates.infrastructure.repository import SupabaseRatesWriter

REPO_MODULE = "app.modules.rates.infrastructure.repository"


class TestApplyManualRateOverride:
    def test_rejects_empty_config_key(self):
        writer = MagicMock()
        with pytest.raises(ValueError):
            apply_manual_rate_override(
                writer, config_key="  ", config_data={"x": 1}, actor_label="admin@eywai"
            )
        writer.save_manual_version.assert_not_called()

    def test_rejects_empty_config_data(self):
        writer = MagicMock()
        with pytest.raises(ValueError):
            apply_manual_rate_override(
                writer, config_key="smic", config_data={}, actor_label="admin@eywai"
            )

    def test_delegates_with_actor_in_comment(self):
        writer = MagicMock()
        writer.save_manual_version.return_value = {
            "config_key": "smic",
            "version": 3,
            "changed": True,
            "id": "row-3",
        }
        result = apply_manual_rate_override(
            writer,
            config_key="smic",
            config_data={"horaire": 11.88},
            actor_label="admin@eywai",
            comment="ajustement",
        )
        assert result["version"] == 3
        kwargs = writer.save_manual_version.call_args.kwargs
        assert kwargs["config_key"] == "smic"
        assert kwargs["new_config_data"] == {"horaire": 11.88}
        assert "admin@eywai" in kwargs["comment"]
        assert "ajustement" in kwargs["comment"]


class TestSaveManualVersion:
    def _writer_with_active(self, active_row):
        """Construit un writer + mock client renvoyant active_row pour le SELECT."""
        client = MagicMock()
        tbl = client.table.return_value
        tbl.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=active_row
        )
        tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": "new-id"}])
        tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return SupabaseRatesWriter(), client, tbl

    def test_creates_v1_when_no_active_config(self):
        writer, client, tbl = self._writer_with_active(None)
        with patch(f"{REPO_MODULE}.get_supabase_admin_client", return_value=client):
            result = writer.save_manual_version(
                config_key="smic",
                new_config_data={"horaire": 11.88},
                comment="Saisie manuelle (admin)",
                source_links=[],
            )
        assert result == {"config_key": "smic", "version": 1, "changed": True, "id": "new-id"}
        assert tbl.insert.called
        inserted_row = tbl.insert.call_args.args[0]
        assert inserted_row["version"] == 1
        assert inserted_row["is_active"] is True

    def test_increments_version_and_deactivates_previous(self):
        active = {"id": "row-2", "version": 2, "config_data": {"horaire": 11.65}}
        writer, client, tbl = self._writer_with_active(active)
        with patch(f"{REPO_MODULE}.get_supabase_admin_client", return_value=client):
            result = writer.save_manual_version(
                config_key="smic",
                new_config_data={"horaire": 11.88},
                comment="Saisie manuelle (admin)",
                source_links=["https://example.org"],
            )
        assert result["version"] == 3
        assert result["changed"] is True
        # désactivation de l'ancienne version + insertion de la nouvelle
        assert tbl.update.called
        assert tbl.insert.called
        inserted_row = tbl.insert.call_args.args[0]
        assert inserted_row["version"] == 3
        assert inserted_row["is_active"] is True

    def test_noop_when_config_data_unchanged(self):
        active = {"id": "row-2", "version": 2, "config_data": {"horaire": 11.88}}
        writer, client, tbl = self._writer_with_active(active)
        with patch(f"{REPO_MODULE}.get_supabase_admin_client", return_value=client):
            result = writer.save_manual_version(
                config_key="smic",
                new_config_data={"horaire": 11.88},
                comment="Saisie manuelle (admin)",
                source_links=[],
            )
        assert result["changed"] is False
        assert result["version"] == 2
        # aucune nouvelle version insérée
        assert not tbl.insert.called
