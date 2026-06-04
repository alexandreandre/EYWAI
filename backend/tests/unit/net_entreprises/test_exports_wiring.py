"""Tests du branchement DSN côté module exports (dégradation gracieuse)."""

from unittest.mock import patch

import pytest

from app.modules.exports.application import service as export_service

pytestmark = pytest.mark.unit


class TestRecordDsnTransmission:
    def test_delegates_to_net_entreprises_service(self):
        expected = {
            "transmission_id": "t1",
            "status": "manual",
            "mode": "manual",
            "message": "msg",
        }
        with patch(
            "app.modules.net_entreprises.application.service.record_and_transmit_dsn",
            return_value=expected,
        ) as mock_ne:
            result = export_service._record_dsn_transmission(
                "c1", "e1", "2025-01", "dsn_mensuelle_normale", b"<DSN/>", "u1"
            )
        assert result == expected
        mock_ne.assert_called_once()

    def test_returns_manual_default_on_exception(self):
        """Si le service net_entreprises plante, la génération DSN n'est pas interrompue."""
        with patch(
            "app.modules.net_entreprises.application.service.record_and_transmit_dsn",
            side_effect=RuntimeError("net down"),
        ):
            result = export_service._record_dsn_transmission(
                "c1", "e1", "2025-01", "dsn_mensuelle_normale", b"<DSN/>", "u1"
            )
        assert result["status"] == "manual"
        assert result["mode"] == "manual"
        assert result["transmission_id"] is None
        assert "net-entreprises.fr" in result["message"]
