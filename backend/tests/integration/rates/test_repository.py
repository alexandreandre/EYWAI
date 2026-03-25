"""
Tests d'intégration du repository rates (SupabaseAllRatesReader).

SupabaseAllRatesReader.get_all_active_rows() : lit les lignes actives de payroll_config.
Avec mock de get_supabase_admin_client pour éviter la DB réelle.
Pour tests contre une DB de test : utiliser la fixture db_session (à compléter dans conftest.py)
et injecter un client Supabase de test ; documenté en commentaire.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.rates.infrastructure.repository import SupabaseAllRatesReader
from app.modules.rates.infrastructure.queries import (
    PAYROLL_CONFIG_TABLE,
    PAYROLL_CONFIG_SELECT_COLUMNS,
)


pytestmark = pytest.mark.integration


class TestSupabaseAllRatesReader:
    """SupabaseAllRatesReader : get_all_active_rows."""

    def test_get_all_active_rows_calls_supabase_with_correct_table_and_filter(self):
        """Vérifie que la table payroll_config est interrogée avec is_active=True."""
        mock_data = [
            {
                "config_key": "cotisations_urssaf",
                "config_data": {},
                "version": 1,
                "last_checked_at": None,
                "is_active": True,
                "created_at": "2025-01-01T00:00:00Z",
                "comment": None,
                "source_links": None,
            }
        ]
        mock_supabase = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=mock_data)
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        with patch(
            "app.modules.rates.infrastructure.repository.get_supabase_admin_client",
            return_value=mock_supabase,
        ):
            reader = SupabaseAllRatesReader()
            result = reader.get_all_active_rows()

        assert result == mock_data
        mock_supabase.table.assert_called_once_with(PAYROLL_CONFIG_TABLE)
        mock_supabase.table.return_value.select.assert_called_once()
        select_call = mock_supabase.table.return_value.select.call_args[0][0]
        assert select_call == ", ".join(PAYROLL_CONFIG_SELECT_COLUMNS)
        mock_supabase.table.return_value.select.return_value.eq.assert_called_once_with(
            "is_active", True
        )

    def test_get_all_active_rows_returns_empty_list_when_no_data(self):
        """Quand Supabase retourne data vide ou None, get_all_active_rows retourne []."""
        mock_supabase = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=None)
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        with patch(
            "app.modules.rates.infrastructure.repository.get_supabase_admin_client",
            return_value=mock_supabase,
        ):
            reader = SupabaseAllRatesReader()
            result = reader.get_all_active_rows()

        assert result == []

    def test_get_all_active_rows_returns_empty_list_when_data_empty_list(self):
        """Quand response.data est [], get_all_active_rows retourne []."""
        mock_supabase = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        with patch(
            "app.modules.rates.infrastructure.repository.get_supabase_admin_client",
            return_value=mock_supabase,
        ):
            reader = SupabaseAllRatesReader()
            result = reader.get_all_active_rows()

        assert result == []


# Fixture à ajouter dans tests/conftest.py si tests contre DB de test réelle :
# @pytest.fixture
# def rates_db_session(db_session):
#     """Session ou client DB pour la table payroll_config (module rates).
#     À compléter : si db_session fournit un client Supabase de test, retourner ce client
#     et insérer des lignes payroll_config (config_key, config_data, version, is_active=True, ...)
#     pour tester get_all_active_rows contre des données réelles."""
#     return db_session
