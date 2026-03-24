"""
Tests unitaires des queries du module dashboard.

Chaque query délègue au service applicatif. On mocke le service pour vérifier
que les queries appellent le bon cas d'usage et retournent le résultat.
"""
from unittest.mock import patch

import pytest

from app.modules.dashboard.application import queries
from app.modules.dashboard.schemas.responses import DashboardData, ResidencePermitStats


# Données factices pour les réponses mockées
COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_minimal_dashboard_data():
    """DashboardData minimal pour tests."""
    from app.modules.dashboard.schemas.responses import (
        ActionItems,
        AlertItems,
        ChartDataPoint,
        KpiData,
        PayrollStatus,
        TeamPulse,
    )
    return DashboardData(
        kpis=KpiData(
            coutTotal=1000.0,
            netVerse=800.0,
            effectifActif=5,
            tauxAbsenteisme=2.5,
            currentMonth="02/2025",
            cdiCount=3,
            cddCount=2,
            contractDistribution={"CDI": 3, "CDD": 2},
        ),
        chartData=[ChartDataPoint(name="Fév", Net_Verse=800.0, Charges=200.0)],
        actions=ActionItems(pendingAbsences=1, pendingExpenses=0),
        alerts=AlertItems(obsoleteRates=0, expiringContracts=0, endOfTrialPeriods=0),
        teamPulse=TeamPulse(absentToday=[], upcomingEvents=[]),
        employees=[],
        payrollStatus=PayrollStatus(currentMonth="March 2025", step=1, totalSteps=4),
    )


def _make_residence_permit_stats():
    return ResidencePermitStats(
        total_expire=0,
        total_a_renouveler=1,
        total_a_renseigner=2,
        total_valide=3,
    )


class TestGetDashboardData:
    """Tests de get_dashboard_data (query)."""

    @patch("app.modules.dashboard.application.queries.build_full_dashboard")
    def test_calls_build_full_dashboard_with_company_id(self, mock_build):
        """get_dashboard_data appelle build_full_dashboard(company_id)."""
        mock_build.return_value = _make_minimal_dashboard_data()
        result = queries.get_dashboard_data(COMPANY_ID)
        mock_build.assert_called_once_with(COMPANY_ID)
        assert result.kpis.effectifActif == 5
        assert result.actions.pendingAbsences == 1

    @patch("app.modules.dashboard.application.queries.build_full_dashboard")
    def test_returns_dashboard_data(self, mock_build):
        """Le résultat est une instance DashboardData."""
        mock_build.return_value = _make_minimal_dashboard_data()
        result = queries.get_dashboard_data(COMPANY_ID)
        assert isinstance(result, DashboardData)
        assert result.kpis.currentMonth == "02/2025"


class TestGetResidencePermitStats:
    """Tests de get_residence_permit_stats (query)."""

    @patch("app.modules.dashboard.application.queries._get_residence_permit_stats")
    def test_calls_service_with_company_id(self, mock_service):
        """get_residence_permit_stats appelle le service avec company_id."""
        mock_service.return_value = _make_residence_permit_stats()
        result = queries.get_residence_permit_stats(COMPANY_ID)
        mock_service.assert_called_once_with(COMPANY_ID)
        assert result.total_valide == 3
        assert result.total_a_renouveler == 1

    @patch("app.modules.dashboard.application.queries._get_residence_permit_stats")
    def test_returns_residence_permit_stats(self, mock_service):
        """Le résultat est une instance ResidencePermitStats."""
        mock_service.return_value = _make_residence_permit_stats()
        result = queries.get_residence_permit_stats(COMPANY_ID)
        assert isinstance(result, ResidencePermitStats)
        assert result.total_expire == 0
        assert result.total_a_renseigner == 2
