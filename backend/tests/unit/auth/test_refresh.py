"""Tests unitaires du renouvellement de session (refresh token)."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.auth.application.refresh import refresh_tokens


class TestRefreshTokens:
    def test_empty_refresh_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            refresh_tokens("")
        assert exc.value.status_code == 401

    def test_valid_refresh_returns_new_tokens(self):
        fake_session = {
            "access_token": "new-jwt",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "expires_at": 9999999999,
        }
        with patch("app.modules.auth.application.refresh.auth_provider") as auth:
            auth.refresh_session.return_value = fake_session
            result = refresh_tokens("old-refresh")

        assert result["access_token"] == "new-jwt"
        assert result["refresh_token"] == "new-refresh"
        auth.refresh_session.assert_called_once_with("old-refresh")

    def test_provider_error_raises_401(self):
        with patch("app.modules.auth.application.refresh.auth_provider") as auth:
            auth.refresh_session.side_effect = Exception("invalid")
            with pytest.raises(HTTPException) as exc:
                refresh_tokens("bad-token")
        assert exc.value.status_code == 401
