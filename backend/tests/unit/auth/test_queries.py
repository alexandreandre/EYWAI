"""
Tests unitaires des queries auth (application/queries.py).

Repository mocké ; pas de DB.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.auth.application import queries
from app.modules.auth.application.dto import VerifyResetTokenResult


class TestVerifyResetToken:
    """Query verify_reset_token."""

    def test_valid_token_returns_result_with_email(self):
        """Token valide et non expiré → VerifyResetTokenResult(valid=True, email)."""
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        with patch("app.modules.auth.application.queries.reset_token_repository") as repo:
            repo.get_valid.return_value = {
                "user_id": "user-123",
                "email": "user@example.com",
                "expires_at": expires,
            }

            result = queries.verify_reset_token("valid-token-abc")

        assert isinstance(result, VerifyResetTokenResult)
        assert result.valid is True
        assert result.email == "user@example.com"

    def test_invalid_or_used_token_raises_400(self):
        """Token invalide ou déjà utilisé → HTTP 400."""
        with patch("app.modules.auth.application.queries.reset_token_repository") as repo:
            repo.get_valid.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                queries.verify_reset_token("invalid-token")

        assert exc_info.value.status_code == 400
        assert "invalide" in exc_info.value.detail.lower()

    def test_expired_token_raises_400(self):
        """Token expiré → HTTP 400."""
        expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with patch("app.modules.auth.application.queries.reset_token_repository") as repo:
            repo.get_valid.return_value = {
                "user_id": "user-123",
                "email": "user@example.com",
                "expires_at": expired,
            }

            with pytest.raises(HTTPException) as exc_info:
                queries.verify_reset_token("expired-token")

        assert exc_info.value.status_code == 400
        assert "expiré" in exc_info.value.detail.lower()


class TestGetMe:
    """Query get_me : retourne l'utilisateur courant."""

    def test_returns_current_user_unchanged(self):
        """get_me retourne tel quel l'objet current_user passé."""
        fake_user = {"id": "u1", "email": "u@example.com", "role": "admin"}

        result = queries.get_me(fake_user)

        assert result is fake_user

    def test_returns_user_object_with_attributes(self):
        """Fonctionne avec un objet ayant des attributs (ex. User Pydantic)."""
        class FakeUser:
            def __init__(self):
                self.id = "user-123"
                self.email = "me@test.com"

        user = FakeUser()
        result = queries.get_me(user)

        assert result is user
        assert result.email == "me@test.com"
