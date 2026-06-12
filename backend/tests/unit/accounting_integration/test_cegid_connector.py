"""Tests connecteur Cegid Loop (httpx mocké) — protocole officiel Loop API.

Auth : x-apikey + Ocp-Apim-Subscription-Key. Import FEC : getFileUrlDeposit →
PUT Azure → importFEC (accountingImportRequestId) → getImportStatus (1/2/3/4).
"""

from unittest.mock import MagicMock, patch

import httpx

from app.modules.accounting_integration.infrastructure.cegid_quadra_connector import (
    CegidQuadraConnector,
    has_complete_cegid_credentials,
    parse_cegid_credentials,
)
from app.shared.utils.secret_store import encrypt_secret


def _full_creds() -> dict:
    return encrypt_secret(
        {
            "loop_apikey": "my-key:my-secret",
            "apim_subscription_key": "sub-key-123",
            "code_dossier": "CEGID003",
        }
    )


class TestCegidCredentials:
    def test_parse_complete(self):
        cfg = {"credentials_ref": _full_creds()}
        creds = parse_cegid_credentials(cfg)
        assert creds is not None
        assert creds.code_dossier == "CEGID003"
        assert has_complete_cegid_credentials(cfg)

    def test_incomplete_missing_subscription(self):
        ref = encrypt_secret({"loop_apikey": "a:b", "code_dossier": "X"})
        assert not has_complete_cegid_credentials({"credentials_ref": ref})


class TestCegidQuadraConnector:
    def _config(self) -> dict:
        return {"enabled": True, "credentials_ref": _full_creds()}

    def test_not_configured_without_credentials(self):
        conn = CegidQuadraConnector()
        result = conn.test_connection({"enabled": True})
        assert result.success is False
        assert result.status == "not_configured"

    def test_invalid_apikey_format(self):
        ref = encrypt_secret(
            {
                "loop_apikey": "no-colon-here",
                "apim_subscription_key": "sub",
                "code_dossier": "CEGID003",
            }
        )
        conn = CegidQuadraConnector()
        result = conn.test_connection({"enabled": True, "credentials_ref": ref})
        assert result.success is False
        assert result.status == "failed"

    @patch(
        "app.modules.accounting_integration.infrastructure.cegid_quadra_connector._request_with_retry"
    )
    def test_connection_success(self, retry_mock):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"depositUrl":"https://blob/x"}'
        resp.json.return_value = {"depositUrl": "https://blob/x"}
        retry_mock.return_value = resp

        conn = CegidQuadraConnector()
        result = conn.test_connection(self._config())
        assert result.success is True
        assert result.status == "connected"
        # Doit cibler getFileUrlDeposit en GET.
        args, kwargs = retry_mock.call_args
        assert args[0] == "GET"
        assert "/getFileUrlDeposit" in args[1]
        headers = kwargs["headers"]
        assert headers["x-apikey"] == "my-key:my-secret"
        assert headers["Ocp-Apim-Subscription-Key"] == "sub-key-123"

    @patch(
        "app.modules.accounting_integration.infrastructure.cegid_quadra_connector._request_with_retry"
    )
    def test_connection_unauthorized(self, retry_mock):
        resp = MagicMock()
        resp.status_code = 401
        resp.content = b""
        retry_mock.return_value = resp

        conn = CegidQuadraConnector()
        result = conn.test_connection(self._config())
        assert result.success is False
        assert result.status == "failed"

    @patch.object(CegidQuadraConnector, "register_fec_import")
    @patch.object(CegidQuadraConnector, "upload_fec_to_deposit")
    @patch.object(CegidQuadraConnector, "get_file_deposit_url")
    def test_submit_fec_success(self, deposit_mock, upload_mock, register_mock):
        deposit_mock.return_value = {
            "uri": "142ae28e-bb2e-4a1d/fec.txt",
            "depositUrl": "https://blob/upload",
        }
        register_mock.return_value = "ca85671e-6f98-4c2e"

        conn = CegidQuadraConnector()
        result = conn.submit_files(
            self._config(),
            [("349536599FEC20260531.txt", b"FECDATA")],
            {"period": "2026-05", "channel": "compta"},
        )
        assert result.success is True
        assert result.status == "sent"
        assert result.external_ref == "ca85671e-6f98-4c2e"
        upload_mock.assert_called_once()
        register_mock.assert_called_once()

    @patch.object(CegidQuadraConnector, "_authenticated_request")
    def test_poll_transmitted(self, auth_mock):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"status":3}'
        resp.json.return_value = {"status": 3}
        auth_mock.return_value = resp

        creds = parse_cegid_credentials(self._config())
        conn = CegidQuadraConnector()
        status, _ = conn.poll_import_status(creds, "ca85671e")
        assert status == "transmitted"

    @patch.object(CegidQuadraConnector, "_authenticated_request")
    def test_poll_failed(self, auth_mock):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"status":4}'
        resp.json.return_value = {"status": 4}
        auth_mock.return_value = resp

        creds = parse_cegid_credentials(self._config())
        conn = CegidQuadraConnector()
        status, _ = conn.poll_import_status(creds, "ca85671e")
        assert status == "failed"

    @patch.object(CegidQuadraConnector, "_authenticated_request")
    def test_poll_in_progress(self, auth_mock):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"status":2}'
        resp.json.return_value = {"status": 2}
        auth_mock.return_value = resp

        creds = parse_cegid_credentials(self._config())
        conn = CegidQuadraConnector()
        status, _ = conn.poll_import_status(creds, "ca85671e")
        assert status == "sent"

    def test_register_fec_import_payload_uri(self):
        creds = parse_cegid_credentials(self._config())
        conn = CegidQuadraConnector()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b'{"accountingImportRequestId":"req-1"}'
        resp.json.return_value = {"accountingImportRequestId": "req-1"}
        with patch.object(
            CegidQuadraConnector, "_authenticated_request", return_value=resp
        ) as auth_mock:
            request_id = conn.register_fec_import(
                creds, {"uri": "guid/fec.txt", "depositUrl": "https://blob/x"}
            )
        assert request_id == "req-1"
        _, kwargs = auth_mock.call_args
        body = kwargs["json_body"]
        assert body["codeIbs"] == "CEGID003"
        assert body["URI"] == "guid/fec.txt"
        assert "URL" not in body

    @patch(
        "app.modules.accounting_integration.infrastructure.cegid_quadra_connector._request_with_retry"
    )
    def test_network_error_on_test(self, retry_mock):
        retry_mock.side_effect = httpx.RequestError("timeout", request=MagicMock())
        conn = CegidQuadraConnector()
        result = conn.test_connection(self._config())
        assert result.success is False
        assert result.status == "failed"
