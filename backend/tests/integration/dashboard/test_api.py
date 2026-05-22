"""
Tests d'intégration HTTP des routes du module dashboard.

Routes : GET /api/dashboard/all, GET /api/dashboard/residence-permit-stats.
Utilise : client (TestClient), dependency_overrides pour get_current_user.
Pour des tests avec token réel, ajouter dans conftest.py une fixture dashboard_headers :
  dashboard_headers : en-têtes pour un utilisateur avec active_company_id et
  has_rh_access_in_company(company_id)=True (format Authorization: Bearer <jwt>,
  optionnel X-Active-Company: <company_id>).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_USER_ID):
    """Utilisateur de test avec droits RH sur l'entreprise et active_company_id."""
    return User(
        id=user_id,
        email="rh@dashboard-test.com",
        first_name="RH",
        last_name="Dashboard",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_user_without_company():
    """Utilisateur sans entreprise active (400 attendu)."""
    return User(
        id=TEST_USER_ID,
        email="noco@test.com",
        first_name="No",
        last_name="Company",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _make_user_without_rh_access(company_id: str = TEST_COMPANY_ID):
    """Utilisateur avec entreprise active mais sans accès RH (403 attendu)."""
    return User(
        id="770e8400-e29b-41d4-a716-446655440002",
        email="emp@test.com",
        first_name="Emp",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


class TestDashboardAll:
    """GET /api/dashboard/all."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token Bearer → 401."""
        response = client.get("/api/dashboard/all")
        assert response.status_code == 401

    def test_with_auth_no_active_company_returns_400(self, client: TestClient):
        """Utilisateur sans entreprise active → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_user_without_company()
        )
        try:
            response = client.get(
                "/api/dashboard/all",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 400
            assert "entreprise active" in (response.json().get("detail") or "").lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_with_auth_no_rh_access_returns_403(self, client: TestClient):
        """Utilisateur sans accès RH sur l'entreprise active → 403."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: (
            _make_user_without_rh_access()
        )
        try:
            response = client.get(
                "/api/dashboard/all",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.dashboard.application.queries.get_dashboard_data")
    def test_with_rh_user_returns_200_and_dashboard_shape(
        self, mock_get_dashboard, client: TestClient
    ):
        """Avec utilisateur RH et mock du service → 200 et structure DashboardData."""
        from app.modules.dashboard.schemas.responses import (
            ActionItems,
            AlertItems,
            ChartDataPoint,
            DashboardData,
            KpiData,
            PayrollStatus,
            TeamPulse,
        )

        mock_get_dashboard.return_value = DashboardData(
            kpis=KpiData(
                coutTotal=1000.0,
                netVerse=800.0,
                effectifActif=3,
                tauxAbsenteisme=1.5,
                currentMonth="02/2025",
                cdiCount=2,
                cddCount=1,
                contractDistribution={"CDI": 2, "CDD": 1},
            ),
            chartData=[ChartDataPoint(name="Fév", Net_Verse=800.0, Charges=200.0)],
            actions=ActionItems(pendingAbsences=1, pendingExpenses=0),
            alerts=AlertItems(
                obsoleteRates=0, expiringContracts=0, endOfTrialPeriods=0
            ),
            teamPulse=TeamPulse(absentToday=[], upcomingEvents=[]),
            employees=[],
            payrollStatus=PayrollStatus(
                currentMonth="March 2025", step=1, totalSteps=4
            ),
        )

        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.get(
                "/api/dashboard/all",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "kpis" in data
            assert "chartData" in data
            assert "actions" in data
            assert "alerts" in data
            assert "teamPulse" in data
            assert "employees" in data
            assert "payrollStatus" in data
            assert data["kpis"]["effectifActif"] == 3
            assert data["actions"]["pendingAbsences"] == 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestDashboardResidencePermitStats:
    """GET /api/dashboard/residence-permit-stats."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/dashboard/residence-permit-stats")
        assert response.status_code == 401

    @patch("app.modules.dashboard.application.queries.get_residence_permit_stats")
    def test_with_rh_user_returns_200_and_stats_shape(
        self, mock_get_stats, client: TestClient
    ):
        """Avec utilisateur RH → 200 et structure ResidencePermitStats."""
        from app.modules.dashboard.schemas.responses import ResidencePermitStats

        mock_get_stats.return_value = ResidencePermitStats(
            total_expire=0,
            total_a_renouveler=2,
            total_a_renseigner=1,
            total_valide=5,
        )

        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.get(
                "/api/dashboard/residence-permit-stats",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "total_expire" in data
            assert "total_a_renouveler" in data
            assert "total_a_renseigner" in data
            assert "total_valide" in data
            assert data["total_valide"] == 5
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestDashboardAnalyticsGestion:
    """GET /api/dashboard/analytics-gestion."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get(
            "/api/dashboard/analytics-gestion",
            params={"period_start": "2026-01-01", "period_end": "2026-01-31"},
        )
        assert response.status_code == 401

    @patch("app.modules.dashboard.application.analytics_gestion.build_analytics_gestion")
    def test_with_rh_user_returns_200_and_shape(
        self, mock_build, client: TestClient
    ):
        from app.modules.dashboard.schemas.analytics_gestion import (
            AnalyticsGestionPeriod,
            AnalyticsGestionResponse,
            CalendriersAnalytics,
            CarriereAnalytics,
            ConformiteAnalytics,
            CseAnalytics,
            EntretiensAnalytics,
            FormationAnalytics,
            MedicalAnalytics,
            ObjectivesAnalytics,
        )

        mock_build.return_value = AnalyticsGestionResponse(
            period=AnalyticsGestionPeriod(
                period_start="2026-01-01",
                period_end="2026-01-31",
                year=2026,
                calendar_year=2026,
                calendar_month=1,
            ),
            entretiens=EntretiensAnalytics(actionable_count=2, overdue_count=1),
            conformite=ConformiteAnalytics(certifications_expired=1),
            formation=FormationAnalytics(budget_consumption_pct=45.0),
            calendriers=CalendriersAnalytics(total=10, a_saisir=3),
            medical=MedicalAnalytics(overdue_count=2),
            objectives=ObjectivesAnalytics(achievement_rate_pct=78.5),
            carriere=CarriereAnalytics(total_promotions=4),
            cse=CseAnalytics(mandate_alerts_count=1),
        )

        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.get(
                "/api/dashboard/analytics-gestion",
                params={"period_start": "2026-01-01", "period_end": "2026-01-31"},
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["entretiens"]["actionable_count"] == 2
            assert data["calendriers"]["a_saisir"] == 3
            assert "medical" in data
            assert "cse" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)
