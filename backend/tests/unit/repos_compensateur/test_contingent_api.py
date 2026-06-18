"""
Tests unitaires endpoints contingent (dependency override + mocks).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.repos_compensateur.api import dependencies


_USER = type("U", (), {"active_company_id": "comp-1"})()


@pytest.fixture
def authed_client():
    app.dependency_overrides[dependencies.get_current_user] = lambda: _USER
    yield TestClient(app)
    app.dependency_overrides.pop(dependencies.get_current_user, None)


class TestContingentSettingsEndpoints:
    @patch("app.modules.repos_compensateur.api.router.get_contingent_settings_row")
    def test_get_settings(self, mock_row, authed_client):
        mock_row.return_value = {
            "company_id": "comp-1",
            "legal_cor_contingent_hours": 220,
            "management_contingent_hours": 360,
            "hours_per_rest_day": 7,
            "include_structural_hours": True,
            "pause_deduction_enabled": False,
            "pause_hs_deduction_per_workday": 0.058765,
            "workdays_per_year_for_pause": 260,
        }
        resp = authed_client.get("/api/repos-compensateur/settings")
        assert resp.status_code == 200
        assert resp.json()["management_contingent_hours"] == 360


class TestContingentOverviewEndpoint:
    @patch("app.modules.repos_compensateur.api.router.get_contingent_overview")
    def test_get_overview(self, mock_overview, authed_client):
        mock_overview.return_value = {
            "company_id": "comp-1",
            "year": 2025,
            "reference_date": "2025-12-31",
            "settings": {
                "company_id": "comp-1",
                "legal_cor_contingent_hours": 220,
                "management_contingent_hours": 360,
                "hours_per_rest_day": 7,
                "include_structural_hours": True,
                "pause_deduction_enabled": False,
                "pause_hs_deduction_per_workday": 0.058765,
                "workdays_per_year_for_pause": 260,
            },
            "kpis": {
                "total_employees": 0,
                "near_limit_count": 0,
                "management_exceeded_count": 0,
                "cor_exceeded_count": 0,
            },
            "employees": [],
        }
        resp = authed_client.get(
            "/api/repos-compensateur/overview?year=2025&reference_date=2025-12-31"
        )
        assert resp.status_code == 200
        assert resp.json()["year"] == 2025
