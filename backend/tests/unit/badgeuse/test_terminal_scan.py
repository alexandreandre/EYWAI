from unittest.mock import patch

from app.modules.badgeuse.application.terminal_service import TerminalContext


@patch("app.modules.badgeuse.api.terminal_router.badgeuse_service.punch_from_qr")
@patch("app.modules.badgeuse.api.terminal_router.enforce_terminal_scan_rate_limit")
def test_terminal_scan_delegates_to_punch_from_qr(mock_rate, mock_punch):
    from app.modules.badgeuse.api.terminal_router import terminal_scan_badge

    mock_punch.return_value = {"employee_id": "emp-1"}
    ctx = TerminalContext(device_id="dev-1", company_id="co-1", label="Usine")
    result = terminal_scan_badge(
        payload={"qr_payload": "eywai:badge:v1:co-1:emp-1:1:sig"},
        request=object(),
        ctx=ctx,
    )
    assert result["employee_id"] == "emp-1"
    mock_punch.assert_called_once()
    kwargs = mock_punch.call_args.kwargs
    assert kwargs["company_id"] == "co-1"
    assert kwargs["terminal_device_id"] == "dev-1"
