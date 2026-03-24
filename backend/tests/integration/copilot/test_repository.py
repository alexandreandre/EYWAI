"""
Tests du module copilot liés à la persistance / accès données.

Le module copilot n'a pas d'entités persistées propres ; le "repository" est un placeholder.
L'accès données passe par infrastructure/queries.py (profiles, employees,
company_collective_agreements, collective_agreement_texts). Ces tests vérifient
le comportement des requêtes avec un client Supabase mocké (pas de DB réelle).

Pour des tests contre une DB de test réelle : ajouter une fixture db_session
dans conftest.py fournissant un client Supabase de test et des données dans
profiles (company_id), employees, company_collective_agreements, etc.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.modules.copilot.infrastructure.queries import (
    get_company_id_for_user,
    get_employees_for_fuzzy_search,
    get_company_collective_agreements,
)


pytestmark = pytest.mark.integration


class TestGetCompanyIdForUser:
    """infrastructure/queries.get_company_id_for_user."""

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_company_id_when_profile_has_it(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"company_id": "company-uuid-123"}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_company_id_for_user("user-uuid-456")

        assert result == "company-uuid-123"
        mock_sb.table.assert_called_once_with("profiles")
        mock_sb.table().select.assert_called_once_with("company_id")
        mock_sb.table().select().eq.assert_called_once_with("id", "user-uuid-456")

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_none_when_no_data(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = None
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_company_id_for_user("user-orphan")

        assert result is None

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_none_when_company_id_empty(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = {"company_id": None}
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_company_id_for_user("user-no-company")

        assert result is None


class TestGetEmployeesForFuzzySearch:
    """infrastructure/queries.get_employees_for_fuzzy_search."""

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_list_of_employees(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "e1", "first_name": "Jean", "last_name": "Dupont", "job_title": "Dev"},
            {"id": "e2", "first_name": "Marie", "last_name": "Martin", "job_title": "RH"},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_employees_for_fuzzy_search()

        assert len(result) == 2
        assert result[0]["first_name"] == "Jean"
        mock_sb.table.assert_called_once_with("employees")
        mock_sb.table().select.assert_called_once()

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_empty_list_when_no_data(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = None
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_employees_for_fuzzy_search()

        assert result == []


class TestGetCompanyCollectiveAgreements:
    """infrastructure/queries.get_company_collective_agreements."""

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_agreements_with_full_text_when_cached(self, mock_get_supabase):
        mock_assign_response = MagicMock()
        mock_assign_response.data = [
            {
                "company_id": "c1",
                "collective_agreements_catalog": {
                    "id": "cat-1",
                    "name": "SYNTEC",
                    "idcc": "1486",
                    "description": "Informatique",
                    "sector": "IT",
                },
            },
        ]
        mock_text_response = MagicMock()
        mock_text_response.data = {"full_text": "Article 1 - Champ d'application..."}

        mock_table_cca = MagicMock()
        mock_table_cca.select.return_value.eq.return_value.execute.return_value = mock_assign_response
        mock_table_ct = MagicMock()
        mock_table_ct.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_text_response

        mock_sb = MagicMock()
        mock_sb.table.side_effect = lambda name: (
            mock_table_cca if name == "company_collective_agreements" else mock_table_ct
        )
        mock_get_supabase.return_value = mock_sb

        result = get_company_collective_agreements("company-123")

        assert len(result) == 1
        assert result[0]["id"] == "cat-1"
        assert result[0]["name"] == "SYNTEC"
        assert result[0]["idcc"] == "1486"
        assert result[0]["full_text"] == "Article 1 - Champ d'application..."
        assert result[0]["has_text_cached"] is True

    @patch("app.modules.copilot.infrastructure.queries.get_supabase_client")
    def test_returns_empty_list_when_no_assignments(self, mock_get_supabase):
        mock_sb = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_get_supabase.return_value = mock_sb

        result = get_company_collective_agreements("company-empty")

        assert result == []
