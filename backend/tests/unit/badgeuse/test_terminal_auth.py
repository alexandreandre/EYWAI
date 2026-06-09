from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.badgeuse.api.terminal_auth import get_badgeuse_terminal_context
from app.modules.badgeuse.application.terminal_service import TerminalContext


def test_get_badgeuse_terminal_context_rejects_missing_token():
    with pytest.raises(HTTPException) as exc:
        get_badgeuse_terminal_context(x_badgeuse_terminal_token=None)
    assert exc.value.status_code == 401


@patch("app.modules.badgeuse.api.terminal_auth.authenticate_terminal")
def test_get_badgeuse_terminal_context_returns_context(mock_auth):
    mock_auth.return_value = TerminalContext(
        device_id="dev-1",
        company_id="co-1",
        label="Entrée usine",
    )
    ctx = get_badgeuse_terminal_context(x_badgeuse_terminal_token="secret")
    assert ctx.device_id == "dev-1"
    assert ctx.company_id == "co-1"
