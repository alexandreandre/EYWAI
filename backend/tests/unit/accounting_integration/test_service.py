"""Tests service intégration comptable."""

from unittest.mock import MagicMock, patch

from app.modules.accounting_integration.application import service
from app.modules.accounting_integration.schemas.responses import TransmitComptaResult


class TestAccountingIntegrationService:
    def test_default_config_not_configured(self):
        with patch(
            "app.modules.accounting_integration.application.service.repository.get_config",
            return_value=None,
        ):
            cfg = service.get_config("co-1")
        assert cfg.enabled is False
        assert cfg.connection_state == "not_configured"

    def test_manual_transmit_ok(self):
        with patch(
            "app.modules.accounting_integration.application.service.repository.get_config",
            return_value={"enabled": True, "mode": "manual", "provider": "manual"},
        ), patch(
            "app.modules.accounting_integration.application.service.repository.get_platform_provider",
            return_value={"enabled": True},
        ), patch(
            "app.modules.accounting_integration.application.service.repository.insert_transmission",
            return_value="tx-1",
        ) as insert_mock:
            result = service.transmit_compta_files(
                "co-1", [], {"period": "2026-05", "channel": "compta"}
            )
        assert result.success is True
        assert result.status == "manual"
        insert_mock.assert_called_once()

    def test_force_manual_skips_api(self):
        with patch(
            "app.modules.accounting_integration.application.service.repository.get_config",
            return_value={
                "enabled": True,
                "mode": "api_quadra",
                "provider": "cegid_quadra",
                "credentials_ref": "enc",
            },
        ), patch(
            "app.modules.accounting_integration.application.service.repository.get_platform_provider",
            return_value={"enabled": True},
        ), patch(
            "app.modules.accounting_integration.application.service.repository.insert_transmission",
            return_value="tx-2",
        ), patch(
            "app.modules.accounting_integration.application.service.resolve_connector",
        ) as resolve_mock:
            result = service.transmit_compta_files(
                "co-1",
                [("fec.csv", b"data")],
                {"period": "2026-05", "channel": "compta"},
                force_manual=True,
            )
        resolve_mock.assert_not_called()
        assert result.status == "manual"

    def test_api_failure_manual_fallback(self):
        connector = MagicMock()
        connector.submit_files.return_value = MagicMock(
            success=False,
            status="failed",
            message="HTTP 500",
            external_ref=None,
        )
        with patch(
            "app.modules.accounting_integration.application.service.repository.get_config",
            return_value={
                "enabled": True,
                "mode": "api_quadra",
                "provider": "cegid_quadra",
                "credentials_ref": "enc",
            },
        ), patch(
            "app.modules.accounting_integration.application.service.repository.get_platform_provider",
            return_value={"enabled": True},
        ), patch(
            "app.modules.accounting_integration.application.service.repository.find_existing_transmission",
            return_value=None,
        ), patch(
            "app.modules.accounting_integration.application.service.repository.insert_transmission",
            return_value="tx-3",
        ), patch(
            "app.modules.accounting_integration.application.service.repository.update_transmission",
        ), patch(
            "app.modules.accounting_integration.application.service.resolve_connector",
            return_value=connector,
        ):
            result = service.transmit_compta_files(
                "co-1",
                [("fec.csv", b"data")],
                {"period": "2026-05", "channel": "compta"},
            )
        assert result.success is False
        assert result.manual_fallback is True
        assert result.status == "failed"

    def test_try_transmit_compat_tuple(self):
        with patch(
            "app.modules.accounting_integration.application.service.transmit_compta_files",
            return_value=TransmitComptaResult(
                success=False,
                status="failed",
                message="Repli manuel",
                manual_fallback=True,
            ),
        ):
            ok, msg = service.try_transmit_compta_files("co-1", [], {"period": "2026-05"})
        assert ok is True
        assert "manuel" in msg.lower() or "repli" in msg.lower()
