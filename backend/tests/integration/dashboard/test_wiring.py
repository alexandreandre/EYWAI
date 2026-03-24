"""
Tests de câblage (wiring) du module dashboard : injection des dépendances et flux bout en bout.

Vérifie que le router dashboard est monté, que les routes répondent (pas 404),
et qu'un enchaînement typique (contexte RH → GET /all) est cohérent.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_rh_user():
    return User(
        id="660e8400-e29b-41d4-a716-446655440001",
        email="rh@test.com",
        first_name="RH",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestDashboardRouterMounted:
    """Vérification que le router dashboard est inclus dans l'app."""

    def test_dashboard_all_responds_not_404(self, client: TestClient):
        """GET /api/dashboard/all répond (401 sans auth, pas 404)."""
        response = client.get("/api/dashboard/all")
        assert response.status_code != 404

    def test_dashboard_residence_permit_stats_responds_not_404(self, client: TestClient):
        """GET /api/dashboard/residence-permit-stats répond (401 sans auth, pas 404)."""
        response = client.get("/api/dashboard/residence-permit-stats")
        assert response.status_code != 404

    def test_unknown_dashboard_route_returns_404(self, client: TestClient):
        """Une route inexistante sous /api/dashboard renvoie 404."""
        response = client.get("/api/dashboard/unknown-route")
        assert response.status_code == 404


class TestDashboardFlowE2E:
    """Flux de bout en bout : auth requise puis appel aux queries."""

    @patch("app.modules.dashboard.application.queries.get_dashboard_data")
    @patch("app.modules.dashboard.application.queries.get_residence_permit_stats")
    def test_rh_user_can_call_all_and_residence_permit_stats(
        self, mock_stats, mock_dashboard, client: TestClient
    ):
        """Utilisateur RH : GET /all puis GET /residence-permit-stats → 200 pour les deux."""
        from app.modules.dashboard.schemas.responses import (
            ActionItems,
            AlertItems,
            ChartDataPoint,
            DashboardData,
            KpiData,
            PayrollStatus,
            ResidencePermitStats,
            TeamPulse,
        )
        mock_dashboard.return_value = DashboardData(
            kpis=KpiData(
                coutTotal=0, netVerse=0, effectifActif=0, tauxAbsenteisme=0,
                currentMonth="01/2025", cdiCount=0, cddCount=0, contractDistribution={},
            ),
            chartData=[ChartDataPoint(name="Jan", Net_Verse=0, Charges=0)],
            actions=ActionItems(pendingAbsences=0, pendingExpenses=0),
            alerts=AlertItems(obsoleteRates=0, expiringContracts=0, endOfTrialPeriods=0),
            teamPulse=TeamPulse(absentToday=[], upcomingEvents=[]),
            employees=[],
            payrollStatus=PayrollStatus(currentMonth="January 2025", step=1, totalSteps=4),
        )
        mock_stats.return_value = ResidencePermitStats(
            total_expire=0, total_a_renouveler=0, total_a_renseigner=0, total_valide=0
        )

        from app.core.security import get_current_user
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            r1 = client.get(
                "/api/dashboard/all",
                headers={"Authorization": "Bearer fake"},
            )
            assert r1.status_code == 200
            assert "kpis" in r1.json()

            r2 = client.get(
                "/api/dashboard/residence-permit-stats",
                headers={"Authorization": "Bearer fake"},
            )
            assert r2.status_code == 200
            assert "total_valide" in r2.json()

            mock_dashboard.assert_called_once_with(TEST_COMPANY_ID)
            mock_stats.assert_called_once_with(TEST_COMPANY_ID)
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.modules.dashboard.application.queries.get_dashboard_data")
    def test_dependency_injection_uses_overridden_user(self, mock_get_dashboard, client: TestClient):
        """L'override de get_current_user est bien utilisé par le router."""
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
                coutTotal=0, netVerse=0, effectifActif=0, tauxAbsenteisme=0,
                currentMonth="01/2025", cdiCount=0, cddCount=0, contractDistribution={},
            ),
            chartData=[ChartDataPoint(name="Jan", Net_Verse=0, Charges=0)],
            actions=ActionItems(pendingAbsences=0, pendingExpenses=0),
            alerts=AlertItems(obsoleteRates=0, expiringContracts=0, endOfTrialPeriods=0),
            teamPulse=TeamPulse(absentToday=[], upcomingEvents=[]),
            employees=[],
            payrollStatus=PayrollStatus(currentMonth="January 2025", step=1, totalSteps=4),
        )
        from app.core.security import get_current_user
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.get(
                "/api/dashboard/all",
                headers={"Authorization": "Bearer any"},
            )
            assert response.status_code == 200
            mock_get_dashboard.assert_called_once_with(TEST_COMPANY_ID)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
