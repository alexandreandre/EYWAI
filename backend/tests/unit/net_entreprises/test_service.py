"""Tests du service applicatif net_entreprises (config masquée, transmission, suivi)."""

from unittest.mock import patch

import pytest

from app.modules.net_entreprises.application import service
from app.modules.net_entreprises.domain.value_objects import (
    TransmissionMode,
    TransmissionStatus,
)

pytestmark = pytest.mark.unit


class TestGetConfigMasking:
    def test_empty_when_no_row(self):
        with patch.object(service.repository, "get_config", return_value=None):
            resp = service.get_config("c1")
        assert resp.enabled is False
        assert resp.connection_state == "not_configured"
        assert resp.has_secret is False

    def test_never_exposes_secret_ref_value(self):
        row = {
            "enabled": True,
            "mode": "manual",
            "siret_declarant": "12345678901234",
            "secret_ref": "set",
            "identifiant": "decl-1",
        }
        with patch.object(service.repository, "get_config", return_value=row):
            resp = service.get_config("c1")
        # has_secret reflète la présence sans divulguer la valeur.
        assert resp.has_secret is True
        dumped = resp.model_dump()
        assert "secret" not in dumped
        assert "secret_ref" not in dumped


class TestUpdateConfig:
    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            service.update_config("c1", {"mode": "bogus"})

    def test_secret_sets_secret_ref(self):
        captured = {}

        def fake_upsert(company_id, fields):
            captured.update(fields)
            return {**fields, "enabled": fields.get("enabled", False), "mode": "manual"}

        with patch.object(service.repository, "upsert_config", side_effect=fake_upsert):
            service.update_config("c1", {"secret": "p4ss", "mode": "manual"}, user_id="u1")
        assert captured.get("secret_ref") == "set"
        assert "secret" not in captured  # le secret en clair n'est pas persisté tel quel


class TestRecordAndTransmit:
    def test_manual_mode_creates_manual_transmission(self):
        with patch.object(service.repository, "get_config", return_value=None), patch.object(
            service.repository, "insert_transmission", return_value="t1"
        ), patch.object(service.repository, "update_transmission") as mock_upd:
            result = service.record_and_transmit_dsn(
                company_id="c1",
                export_id="e1",
                period="2025-01",
                dsn_type="dsn_mensuelle_normale",
                xml_content=b"<DSN/>",
                user_id="u1",
            )
        assert result["transmission_id"] == "t1"
        assert result["status"] == TransmissionStatus.MANUAL.value
        assert result["mode"] == TransmissionMode.MANUAL.value
        mock_upd.assert_called()

    def test_api_mode_falls_back_to_manual_when_not_configured(self):
        config = {"enabled": True, "mode": "api_certificat"}
        with patch.object(service.settings, "NET_ENTREPRISES_ENABLED", True), patch.object(
            service.repository, "get_config", return_value=config
        ), patch.object(
            service.repository, "insert_transmission", return_value="t2"
        ), patch.object(service.repository, "update_transmission") as mock_upd:
            result = service.record_and_transmit_dsn(
                company_id="c1",
                export_id="e1",
                period="2025-02",
                dsn_type="dsn_mensuelle_normale",
                xml_content=b"<DSN/>",
                user_id="u1",
            )
        # L'API stub lève NotConfigured → fallback manuel, sans planter.
        assert result["status"] == TransmissionStatus.MANUAL.value
        assert result["mode"] == TransmissionMode.MANUAL.value
        mock_upd.assert_called()


class TestMarkTransmitted:
    def test_unknown_transmission_raises_lookup(self):
        with patch.object(service.repository, "get_transmission", return_value=None):
            with pytest.raises(LookupError):
                service.mark_transmitted("c1", "tX", None)

    def test_marks_acknowledged_with_ref(self):
        existing = {"id": "t1", "status": "manual", "period": "2025-01"}
        with patch.object(
            service.repository, "get_transmission", return_value=existing
        ), patch.object(
            service.repository,
            "update_transmission",
            side_effect=lambda tid, fields: {**existing, **fields},
        ):
            entry = service.mark_transmitted("c1", "t1", "DEPOT-123")
        assert entry.status == TransmissionStatus.ACKNOWLEDGED.value
        assert entry.net_entreprises_ref == "DEPOT-123"


class TestConnectionTestNeverRaises:
    def test_test_connection_handles_connector_exception(self):
        class Boom:
            mode = "manual"

            def test_connection(self, _):
                raise RuntimeError("boom")

        with patch.object(service.repository, "get_config", return_value=None), patch.object(
            service, "resolve_connector", return_value=Boom()
        ), patch.object(service.repository, "update_test_result"):
            res = service.test_connection("c1")
        assert res.success is False
        assert res.status == "failure"
