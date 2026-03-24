"""
Tests d'intégration du repository auth : PasswordResetTokenRepository.

Vérifie les opérations CRUD / métier sur les tokens de réinitialisation.
Avec une DB de test (fixture db_session) : tests réels contre la table password_resets.
Sans DB de test : mocks Supabase pour valider la logique et les appels.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.auth.infrastructure.repository import PasswordResetTokenRepository


@pytest.mark.integration
class TestPasswordResetTokenRepository:
    """PasswordResetTokenRepository : create, get_valid, mark_used."""

    def test_create_calls_supabase_insert_with_correct_data(self):
        """create() appelle supabase.table().insert() avec user_id, email (lower), token, expires_at, used=False."""
        with patch("app.modules.auth.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            table_mock.insert.return_value = chain
            supabase.table.return_value = table_mock

            repo = PasswordResetTokenRepository()
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            repo.create(
                user_id="user-1",
                email="User@Example.COM",
                token="tok-abc",
                expires_at=expires,
            )

            table_mock.insert.assert_called_once()
            call_data = table_mock.insert.call_args[0][0]
            assert call_data["user_id"] == "user-1"
            assert call_data["email"] == "user@example.com"
            assert call_data["token"] == "tok-abc"
            assert call_data["expires_at"] == expires
            assert call_data["used"] is False

    def test_get_valid_returns_none_when_no_data(self):
        """get_valid() retourne None quand la requête ne renvoie aucune ligne."""
        with patch("app.modules.auth.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            table.select.return_value = select_chain
            supabase.table.return_value = table

            repo = PasswordResetTokenRepository()
            result = repo.get_valid("unknown-token")

        assert result is None

    def test_get_valid_returns_first_row_when_data_exists(self):
        """get_valid() retourne la première ligne si token valide et non utilisé."""
        row = {
            "user_id": "u1",
            "email": "u@ex.com",
            "token": "valid-tok",
            "expires_at": "2026-12-31T12:00:00Z",
            "used": False,
        }
        with patch("app.modules.auth.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            select_chain = MagicMock()
            select_chain.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[row]
            )
            table.select.return_value = select_chain
            supabase.table.return_value = table

            repo = PasswordResetTokenRepository()
            result = repo.get_valid("valid-tok")

        assert result == row
        table.select.assert_called_once_with("*")
        select_chain.eq.assert_any_call("token", "valid-tok")
        select_chain.eq.return_value.eq.assert_called_with("used", False)

    def test_mark_used_calls_update_then_eq_then_execute(self):
        """mark_used() appelle update(used=True) puis eq("token", token) puis execute()."""
        with patch("app.modules.auth.infrastructure.repository.supabase") as supabase:
            table = MagicMock()
            update_chain = MagicMock()
            table.update.return_value = update_chain
            update_chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = PasswordResetTokenRepository()
            repo.mark_used("tok-xyz")

            table.update.assert_called_once_with({"used": True})
            update_chain.eq.assert_called_once_with("token", "tok-xyz")
            update_chain.eq.return_value.execute.assert_called_once()
