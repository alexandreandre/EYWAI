"""Tests fabrique connecteurs comptables."""

from unittest.mock import patch

from app.modules.accounting_integration.infrastructure.cegid_quadra_connector import (
    CegidQuadraConnector,
)
from app.modules.accounting_integration.infrastructure.connector_factory import (
    resolve_connector,
)
from app.modules.accounting_integration.infrastructure.manual_connector import (
    ManualAccountingConnector,
)


class TestConnectorFactory:
    def test_force_manual_returns_manual(self):
        conn = resolve_connector(
            {"enabled": True, "mode": "api_quadra", "provider": "cegid_quadra"},
            {"enabled": True},
            force_manual=True,
        )
        assert isinstance(conn, ManualAccountingConnector)

    def test_disabled_config_returns_manual(self):
        conn = resolve_connector({"enabled": False}, None)
        assert isinstance(conn, ManualAccountingConnector)

    def test_platform_disabled_returns_manual(self):
        conn = resolve_connector(
            {"enabled": True, "mode": "api_quadra", "provider": "cegid_quadra"},
            {"enabled": False},
        )
        assert isinstance(conn, ManualAccountingConnector)

    @patch(
        "app.modules.accounting_integration.infrastructure.connector_factory._api_globally_enabled",
        return_value=True,
    )
    def test_cegid_when_api_enabled(self, _mock):
        from app.shared.utils.secret_store import encrypt_secret

        creds = encrypt_secret(
            {
                "loop_apikey": "k:s",
                "apim_subscription_key": "sub",
                "code_dossier": "DOS",
            }
        )
        conn = resolve_connector(
            {
                "enabled": True,
                "mode": "api_quadra",
                "provider": "cegid_quadra",
                "credentials_ref": creds,
            },
            {"enabled": True, "settings": {}},
        )
        assert isinstance(conn, CegidQuadraConnector)

    @patch(
        "app.modules.accounting_integration.infrastructure.connector_factory._api_globally_enabled",
        return_value=True,
    )
    def test_cegid_shared_platform_keys(self, _mock):
        platform = {
            "enabled": True,
            "platform_credentials_ref": __import__(
                "app.shared.utils.secret_store", fromlist=["encrypt_secret"]
            ).encrypt_secret(
                {
                    "loop_apikey": "k:s",
                    "apim_subscription_key": "sub",
                }
            ),
        }
        conn = resolve_connector(
            {
                "enabled": True,
                "mode": "api_quadra",
                "provider": "cegid_quadra",
                "code_dossier_cegid": "FIL001",
                "cegid_auth_mode": "shared",
            },
            platform,
        )
        assert isinstance(conn, CegidQuadraConnector)

    @patch(
        "app.modules.accounting_integration.infrastructure.connector_factory._api_globally_enabled",
        return_value=False,
    )
    def test_cegid_fallback_when_api_disabled(self, _mock):
        conn = resolve_connector(
            {"enabled": True, "mode": "api_quadra", "provider": "cegid_quadra"},
            {"enabled": True},
        )
        assert isinstance(conn, ManualAccountingConnector)
