"""
Tests d'intégration du repository companies (SupabaseCompanyRepository).

Sans DB de test : mocks Supabase pour valider la logique et les appels.
Avec DB de test : utiliser la fixture db_session (conftest) pour des tests CRUD réels
contre la table companies.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.companies.infrastructure.repository import SupabaseCompanyRepository


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestSupabaseCompanyRepositoryGetById:
    """get_by_id."""

    def test_get_by_id_returns_data_when_found(self):
        """Retourne la ligne company quand elle existe."""
        row = {
            "id": COMPANY_ID,
            "company_name": "Test SARL",
            "siret": "12345678901234",
            "settings": {"medical_follow_up_enabled": True},
            "is_active": True,
        }
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=row
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            result = repo.get_by_id(COMPANY_ID)

            assert result == row
            table.select.assert_called_once_with("*")
            chain.eq.assert_called_once_with("id", COMPANY_ID)

    def test_get_by_id_returns_none_when_not_found(self):
        """Retourne None quand single() ne renvoie pas de ligne."""
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.single.return_value.execute.return_value = MagicMock(
                data=None
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            result = repo.get_by_id("unknown-id")

            assert result is None


class TestSupabaseCompanyRepositoryGetSettings:
    """get_settings."""

    def test_get_settings_returns_settings_column(self):
        """Retourne le contenu de la colonne settings."""
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data={"settings": {"medical_follow_up_enabled": True}})
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            result = repo.get_settings(COMPANY_ID)

            assert result == {"medical_follow_up_enabled": True}
            table.select.assert_called_once_with("settings")
            chain.eq.assert_called_once_with("id", COMPANY_ID)

    def test_get_settings_returns_empty_dict_when_null(self):
        """Retourne {} quand settings est null en base."""
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data={"settings": None})
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            result = repo.get_settings(COMPANY_ID)

            assert result == {}

    def test_get_settings_returns_none_when_company_absent(self):
        """Retourne None quand maybe_single ne renvoie pas de ligne (data vide)."""
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            chain.eq.return_value.maybe_single.return_value.execute.return_value = (
                MagicMock(data=None)
            )
            table.select.return_value = chain
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            result = repo.get_settings("unknown-id")

            assert result is None


class TestSupabaseCompanyRepositoryUpdateSettings:
    """update_settings."""

    def test_update_settings_calls_update_eq_execute(self):
        """Appelle update(settings) puis eq(id) puis execute()."""
        new_settings = {"medical_follow_up_enabled": True, "other": "value"}
        with patch(
            "app.modules.companies.infrastructure.repository.supabase"
        ) as supabase:
            table = MagicMock()
            chain = MagicMock()
            table.update.return_value = chain
            chain.eq.return_value.execute.return_value = None
            supabase.table.return_value = table

            repo = SupabaseCompanyRepository()
            repo.update_settings(COMPANY_ID, new_settings)

            table.update.assert_called_once_with({"settings": new_settings})
            chain.eq.assert_called_once_with("id", COMPANY_ID)
            chain.eq.return_value.execute.assert_called_once()
