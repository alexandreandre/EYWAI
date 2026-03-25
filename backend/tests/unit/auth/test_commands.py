"""
Tests unitaires des commandes auth (application/commands.py).

Repositories et providers mockés ; pas de DB ni HTTP.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.auth.application import commands


class TestRequestPasswordReset:
    """Commande request_password_reset."""

    def test_user_found_sends_email_and_returns_message(self):
        """Si l'utilisateur existe, token créé, email envoyé, message générique retourné."""
        with (
            patch("app.modules.auth.application.commands.auth_provider") as auth,
            patch(
                "app.modules.auth.application.commands.get_profile_display_name"
            ) as get_name,
            patch(
                "app.modules.auth.application.commands.reset_token_repository"
            ) as repo,
            patch("app.modules.auth.application.commands.email_sender") as email,
        ):
            auth.find_user_id_by_email.return_value = "user-uuid-123"
            get_name.return_value = "Jean Dupont"
            email.send_password_reset.return_value = True

            result = commands.request_password_reset("user@example.com")

        assert result == {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }
        auth.find_user_id_by_email.assert_called_once_with("user@example.com")
        get_name.assert_called_once()
        repo.create.assert_called_once()
        assert repo.create.call_args[1]["email"] == "user@example.com"
        email.send_password_reset.assert_called_once()

    def test_user_not_found_returns_same_message_no_exception(self):
        """Si l'email n'existe pas, on retourne le même message (sécurité)."""
        with (
            patch("app.modules.auth.application.commands.auth_provider") as auth,
            patch(
                "app.modules.auth.application.commands.reset_token_repository"
            ) as repo,
            patch("app.modules.auth.application.commands.email_sender") as email,
        ):
            auth.find_user_id_by_email.return_value = None

            result = commands.request_password_reset("inconnu@example.com")

        assert result == {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }
        repo.create.assert_not_called()
        email.send_password_reset.assert_not_called()

    def test_find_user_raises_returns_same_message(self):
        """Si find_user_id_by_email lève, on retourne le message sans propager."""
        with patch("app.modules.auth.application.commands.auth_provider") as auth:
            auth.find_user_id_by_email.side_effect = Exception("DB error")

            result = commands.request_password_reset("user@example.com")

        assert result == {
            "message": "Si cet e-mail existe, un lien de réinitialisation a été envoyé"
        }


class TestResetPassword:
    """Commande reset_password."""

    def test_valid_token_updates_password_and_marks_used(self):
        """Token valide : update password, mark_used, message succès."""
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        with (
            patch(
                "app.modules.auth.application.commands.reset_token_repository"
            ) as repo,
            patch("app.modules.auth.application.commands.auth_provider") as auth,
        ):
            repo.get_valid.return_value = {
                "user_id": "user-123",
                "email": "user@example.com",
                "expires_at": expires,
            }

            result = commands.reset_password("valid-token-xyz", "NewSecureP@ss")

        assert result == {"message": "Mot de passe réinitialisé avec succès"}
        auth.update_user_password.assert_called_once_with("user-123", "NewSecureP@ss")
        repo.mark_used.assert_called_once_with("valid-token-xyz")

    def test_invalid_token_raises_400(self):
        """Token invalide ou déjà utilisé → HTTP 400."""
        with (
            patch(
                "app.modules.auth.application.commands.reset_token_repository"
            ) as repo,
            patch("app.modules.auth.application.commands.auth_provider") as auth,
        ):
            repo.get_valid.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                commands.reset_password("invalid-token", "NewP@ss")

        assert exc_info.value.status_code == 400
        assert (
            "invalide" in exc_info.value.detail.lower()
            or "expiré" in exc_info.value.detail.lower()
        )
        auth.update_user_password.assert_not_called()


class TestChangePassword:
    """Commande change_password (utilisateur connecté)."""

    def test_current_password_ok_updates_and_returns_message(self):
        """Mot de passe actuel correct → update, message succès."""
        with patch("app.modules.auth.application.commands.auth_provider") as auth:
            auth.sign_in_with_password.return_value = {}
            auth.update_user_password.return_value = None

            result = commands.change_password(
                user_id="user-123",
                user_email="user@example.com",
                current_password="OldPass",
                new_password="NewP@ss",
            )

        assert result == {"message": "Mot de passe modifié avec succès"}
        auth.sign_in_with_password.assert_called_once_with(
            "user@example.com", "OldPass"
        )
        auth.update_user_password.assert_called_once_with("user-123", "NewP@ss")

    def test_current_password_wrong_raises_400(self):
        """Mot de passe actuel incorrect → HTTP 400."""
        with patch("app.modules.auth.application.commands.auth_provider") as auth:
            auth.sign_in_with_password.side_effect = Exception("Invalid credentials")

            with pytest.raises(HTTPException) as exc_info:
                commands.change_password(
                    user_id="user-123",
                    user_email="user@example.com",
                    current_password="WrongPass",
                    new_password="NewP@ss",
                )

        assert exc_info.value.status_code == 400
        assert (
            "actuel" in exc_info.value.detail.lower()
            or "incorrect" in exc_info.value.detail.lower()
        )
        auth.update_user_password.assert_not_called()


class TestLogout:
    """Commande logout."""

    def test_sign_out_called_returns_message(self):
        """sign_out appelé, retourne message de déconnexion."""
        with patch("app.modules.auth.application.commands.auth_provider") as auth:
            result = commands.logout()

        assert result == {"message": "Déconnexion réussie"}
        auth.sign_out.assert_called_once()

    def test_sign_out_raises_still_returns_message(self):
        """Même si sign_out lève, on retourne message (comportement legacy)."""
        with patch("app.modules.auth.application.commands.auth_provider") as auth:
            auth.sign_out.side_effect = Exception("Network error")

            result = commands.logout()

        assert result == {"message": "Déconnexion réussie"}
