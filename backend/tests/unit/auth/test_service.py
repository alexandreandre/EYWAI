"""
Tests unitaires du service auth (application/service.py) : login.

Résolution identifiant (email vs username), sign_in, récupération user via token.
Dépendances mockées : is_email_like (règle), user_resolver, auth_provider, user_from_token.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.modules.auth.application.service import login


class TestLoginWithEmail:
    """Login avec email (is_email_like True)."""

    def test_email_and_valid_password_returns_token_and_user(self):
        """Email + mot de passe valide → access_token, token_type, user."""
        fake_session = {"access_token": "jwt-xyz-123"}
        fake_user = MagicMock()
        fake_user.is_super_admin = False

        with (
            patch("app.modules.auth.application.service.auth_provider") as auth,
            patch("app.modules.auth.application.service.user_from_token") as user_ft,
        ):
            auth.sign_in_with_password.return_value = fake_session
            user_ft.get_user.return_value = fake_user

            result = login("user@example.com", "SecretP@ss")

        assert result["access_token"] == "jwt-xyz-123"
        assert result["token_type"] == "bearer"
        assert result["user"] is fake_user
        auth.sign_in_with_password.assert_called_once_with("user@example.com", "SecretP@ss")
        user_ft.get_user.assert_called_once_with("jwt-xyz-123")

    def test_email_and_invalid_password_raises_400(self):
        """Email + mauvais mot de passe → HTTP 400."""
        with patch("app.modules.auth.application.service.auth_provider") as auth:
            auth.sign_in_with_password.side_effect = Exception("Invalid login")

            with pytest.raises(HTTPException) as exc_info:
                login("user@example.com", "WrongPass")

        assert exc_info.value.status_code == 400
        assert "Identifiant" in exc_info.value.detail or "mot de passe" in exc_info.value.detail


class TestLoginWithUsername:
    """Login avec username (is_email_like False) : résolution email puis sign_in."""

    def test_username_resolved_then_login_succeeds(self):
        """Username résolu en email → sign_in avec cet email → token + user."""
        fake_session = {"access_token": "jwt-abc"}
        fake_user = MagicMock()

        with (
            patch("app.modules.auth.application.service.user_resolver") as resolver,
            patch("app.modules.auth.application.service.auth_provider") as auth,
            patch("app.modules.auth.application.service.user_from_token") as user_ft,
        ):
            resolver.resolve_email.return_value = "resolved@example.com"
            auth.sign_in_with_password.return_value = fake_session
            user_ft.get_user.return_value = fake_user

            result = login("jdupont", "P@ssw0rd")

        assert result["access_token"] == "jwt-abc"
        resolver.resolve_email.assert_called_once_with("jdupont")
        auth.sign_in_with_password.assert_called_once_with("resolved@example.com", "P@ssw0rd")

    def test_username_not_found_raises_400(self):
        """Username inconnu (resolve_email → None) → HTTP 400."""
        with (
            patch("app.modules.auth.application.service.user_resolver") as resolver,
            patch("app.modules.auth.application.service.auth_provider") as auth,
        ):
            resolver.resolve_email.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                login("unknown_user", "SomePass")

        assert exc_info.value.status_code == 400
        auth.sign_in_with_password.assert_not_called()

    def test_username_empty_after_strip_raises_400(self):
        """Input vide ou seulement espaces après strip → pas d'email → peut échouer en résolution."""
        with patch("app.modules.auth.application.service.user_resolver") as resolver:
            resolver.resolve_email.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                login("   ", "pass")

        assert exc_info.value.status_code == 400


class TestLoginInputNormalization:
    """Normalisation de l'input (strip, lower)."""

    def test_email_lowercased(self):
        """L'email est passé en lower au sign_in."""
        with (
            patch("app.modules.auth.application.service.auth_provider") as auth,
            patch("app.modules.auth.application.service.user_from_token") as user_ft,
        ):
            auth.sign_in_with_password.return_value = {"access_token": "t"}
            user_ft.get_user.return_value = MagicMock()

            login("User@Example.COM", "pwd")

        auth.sign_in_with_password.assert_called_once_with("user@example.com", "pwd")
