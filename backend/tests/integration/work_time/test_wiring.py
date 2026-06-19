"""Tests intégration wiring — temps de travail généralisable."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-work-time-wiring"


def _rh_user() -> User:
    return User(
        id="user-rh-worktime",
        email="rh@worktime.test",
        first_name="RH",
        last_name="WorkTime",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            )
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestWorkTimeRoutesMounted:
    def test_cp_seniority_without_auth_returns_401(self, client: TestClient):
        assert client.get("/api/absences/cp-seniority-settings").status_code == 401

    def test_modulation_without_auth_returns_401(self, client: TestClient):
        assert client.get("/api/modulation/settings").status_code == 401

    def test_payroll_variables_without_auth_returns_401(self, client: TestClient):
        assert client.get("/api/payroll-variables/rules").status_code == 401

    def test_cp_seniority_settings_wiring(self, client: TestClient):
        rh = _rh_user()
        with patch(
            "app.modules.absences.api.router.cp_seniority_queries.get_cp_seniority_settings"
        ) as mock_get:
            mock_get.return_value = {
                "company_id": TEST_COMPANY_ID,
                "enabled": True,
                "configured": True,
                "preset": "lewis_agreement",
                "seniority_reference": "cp_period_end",
                "seniority_basis": "company_only",
                "counting_unit": "ouvrable",
                "rules": {"mode": "cumulative_rules", "tiers": []},
                "forfait_annual_days_default": 218,
                "forfait_reduction_enabled": True,
                "company_agreement_overrides": False,
            }
            app.dependency_overrides[get_current_user] = lambda: rh
            try:
                resp = client.get("/api/absences/cp-seniority-settings")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert resp.status_code == 200
            assert resp.json()["preset"] == "lewis_agreement"

    def test_modulation_settings_wiring(self, client: TestClient):
        rh = _rh_user()
        with patch(
            "app.modules.modulation.api.router.queries.get_modulation_settings"
        ) as mock_get:
            from app.modules.modulation.schemas.requests import ModulationSettingsResponse

            mock_get.return_value = ModulationSettingsResponse(
                company_id=TEST_COMPANY_ID,
                enabled=True,
                configured=True,
                reference_period_months=12,
                average_weekly_hours=35,
                weekly_high_hours=37,
                weekly_low_hours=32,
                high_weeks_per_cycle=1,
                low_weeks_per_cycle=1,
                cycle_start_week_iso=None,
                pay_smoothed=True,
                weekly_cap_hours=44,
                theoretical_annual_hours=None,
                hour_account_enabled=True,
                hs_franchise_hours_per_period=14,
                hs_franchise_period="month",
                max_account_balance_hours=None,
                account_credit_source="overtime_only",
                recovery_absence_enabled=True,
                recovery_debit_timing="on_validation",
            )
            app.dependency_overrides[get_current_user] = lambda: rh
            try:
                resp = client.get("/api/modulation/settings")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert resp.status_code == 200
            assert resp.json()["weekly_high_hours"] == 37

    def test_payroll_variables_generate_wiring(self, client: TestClient):
        rh = _rh_user()
        with patch(
            "app.modules.payroll_variables.api.router.generate_monthly_variables"
        ) as mock_gen:
            mock_gen.return_value = {
                "company_id": TEST_COMPANY_ID,
                "year": 2026,
                "month": 5,
                "dry_run": True,
                "preview": [],
                "written_count": 0,
            }
            app.dependency_overrides[get_current_user] = lambda: rh
            try:
                resp = client.post(
                    "/api/payroll-variables/generate?year=2026&month=5&dry_run=true"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert resp.status_code == 200
            mock_gen.assert_called_once()
