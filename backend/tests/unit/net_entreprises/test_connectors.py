"""Tests des connecteurs (manuel = no-op, API = stub guardé)."""

import pytest

from app.modules.net_entreprises.domain.interfaces import NetEntreprisesNotConfigured
from app.modules.net_entreprises.domain.value_objects import (
    TransmissionMode,
    TransmissionStatus,
)
from app.modules.net_entreprises.infrastructure.api_connector import (
    NetEntreprisesApiConnector,
)
from app.modules.net_entreprises.infrastructure.manual_connector import (
    ManualNetEntreprisesConnector,
)

pytestmark = pytest.mark.unit


class TestManualConnector:
    def test_test_connection_success_manual(self):
        c = ManualNetEntreprisesConnector()
        res = c.test_connection({})
        assert res.success is True
        assert res.status == "manual"

    def test_submit_returns_manual_status(self):
        c = ManualNetEntreprisesConnector()
        res = c.submit_dsn({}, b"<DSN/>", {"period": "2025-01"})
        assert res.status == TransmissionStatus.MANUAL.value
        assert res.mode == TransmissionMode.MANUAL.value

    def test_get_status_is_none(self):
        c = ManualNetEntreprisesConnector()
        assert c.get_status({}, "ref-1") is None


class TestApiConnectorStub:
    def test_test_connection_not_configured(self):
        c = NetEntreprisesApiConnector()
        res = c.test_connection({})
        assert res.success is False
        assert res.status == "not_configured"

    def test_submit_raises_not_configured(self):
        c = NetEntreprisesApiConnector()
        with pytest.raises(NetEntreprisesNotConfigured):
            c.submit_dsn({}, b"<DSN/>", {"period": "2025-01"})
