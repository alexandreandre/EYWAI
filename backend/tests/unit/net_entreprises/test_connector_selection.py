"""Tests de sélection du connecteur Net-entreprises (fallback manuel)."""

from unittest.mock import patch

import pytest

from app.modules.net_entreprises.application import service
from app.modules.net_entreprises.infrastructure.api_connector import (
    NetEntreprisesApiConnector,
)
from app.modules.net_entreprises.infrastructure.manual_connector import (
    ManualNetEntreprisesConnector,
)

pytestmark = pytest.mark.unit


class TestResolveConnector:
    def test_none_config_returns_manual(self):
        assert isinstance(service.resolve_connector(None), ManualNetEntreprisesConnector)

    def test_disabled_config_returns_manual(self):
        config = {"enabled": False, "mode": "api_certificat"}
        assert isinstance(service.resolve_connector(config), ManualNetEntreprisesConnector)

    def test_enabled_manual_mode_returns_manual(self):
        config = {"enabled": True, "mode": "manual"}
        assert isinstance(service.resolve_connector(config), ManualNetEntreprisesConnector)

    def test_enabled_api_but_global_flag_off_returns_manual(self):
        """Même config API activée, si le flag global est off → manuel."""
        config = {"enabled": True, "mode": "api_certificat"}
        with patch.object(service.settings, "NET_ENTREPRISES_ENABLED", False):
            assert isinstance(
                service.resolve_connector(config), ManualNetEntreprisesConnector
            )

    def test_enabled_api_with_global_flag_on_returns_api(self):
        config = {"enabled": True, "mode": "api_certificat"}
        with patch.object(service.settings, "NET_ENTREPRISES_ENABLED", True):
            assert isinstance(
                service.resolve_connector(config), NetEntreprisesApiConnector
            )


class TestConnectionState:
    def test_not_configured_when_none(self):
        assert service._connection_state(None) == "not_configured"

    def test_manual_when_enabled_manual(self):
        assert service._connection_state({"enabled": True, "mode": "manual"}) == "manual"

    def test_connected_when_enabled_api_and_flag_on(self):
        with patch.object(service.settings, "NET_ENTREPRISES_ENABLED", True):
            state = service._connection_state({"enabled": True, "mode": "api_declarant"})
            assert state == "connected"

    def test_not_configured_when_disabled(self):
        assert service._connection_state({"enabled": False, "mode": "manual"}) == "not_configured"
