"""
Tests des queries du module copilot (application/queries.py).

Repositories / service mockés : pas d'appel réel à la DB.
"""
from unittest.mock import patch

import pytest

from app.modules.copilot.application.queries import get_company_id_for_user_query


pytestmark = pytest.mark.unit


class TestGetCompanyIdForUserQuery:
    """Query get_company_id_for_user_query : résolution du company_id pour un user."""

    @patch("app.modules.copilot.application.queries.get_company_id_for_user")
    def test_returns_company_id_when_found(self, mock_get_company):
        mock_get_company.return_value = "company-uuid-123"
        result = get_company_id_for_user_query("user-uuid-456")
        assert result == "company-uuid-123"
        mock_get_company.assert_called_once_with("user-uuid-456")

    @patch("app.modules.copilot.application.queries.get_company_id_for_user")
    def test_returns_none_when_user_has_no_company(self, mock_get_company):
        mock_get_company.return_value = None
        result = get_company_id_for_user_query("user-orphan")
        assert result is None
        mock_get_company.assert_called_once_with("user-orphan")
