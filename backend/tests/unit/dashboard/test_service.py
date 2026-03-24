"""
Tests unitaires du service applicatif dashboard.

build_full_dashboard et get_residence_permit_stats avec repository et
calculator mockés. Aucune DB ni appel externe.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.dashboard.application.service import (
    build_full_dashboard,
    get_residence_permit_stats,
)
from app.modules.dashboard.schemas.responses import (
    DashboardData,
    ResidencePermitStats,
)


COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestGetResidencePermitStats:
    """Tests de get_residence_permit_stats (service)."""

    @patch("app.modules.dashboard.application.service.get_dashboard_repository")
    @patch("app.modules.dashboard.application.service.get_residence_permit_calculator")
    def test_aggregates_status_counts(
        self, mock_get_calc, mock_get_repo
    ):
        """Agrège correctement les statuts (expired, to_renew, to_complete, valid)."""
        mock_repo = MagicMock()
        mock_repo.get_employees_for_residence_permit_stats.return_value = [
            {
                "id": "e1",
                "is_subject_to_residence_permit": True,
                "residence_permit_expiry_date": "2026-12-31",
                "employment_status": "actif",
            },
            {
                "id": "e2",
                "is_subject_to_residence_permit": True,
                "residence_permit_expiry_date": "2025-01-01",  # passé
                "employment_status": "actif",
            },
        ]
        mock_get_repo.return_value = mock_repo

        calc = MagicMock()
        calc.calculate_residence_permit_status.side_effect = [
            {"residence_permit_status": "valid"},
            {"residence_permit_status": "expired"},
        ]
        mock_get_calc.return_value = calc

        result = get_residence_permit_stats(COMPANY_ID)

        assert isinstance(result, ResidencePermitStats)
        assert result.total_valide == 1
        assert result.total_expire == 1
        assert result.total_a_renouveler == 0
        assert result.total_a_renseigner == 0
        mock_repo.get_employees_for_residence_permit_stats.assert_called_once_with(
            COMPANY_ID
        )

    @patch("app.modules.dashboard.application.service.get_dashboard_repository")
    @patch("app.modules.dashboard.application.service.get_residence_permit_calculator")
    def test_empty_employees_returns_zeros(self, mock_get_calc, mock_get_repo):
        """Sans employés soumis au titre de séjour, tous les comptes à 0."""
        mock_repo = MagicMock()
        mock_repo.get_employees_for_residence_permit_stats.return_value = []
        mock_get_repo.return_value = mock_repo

        result = get_residence_permit_stats(COMPANY_ID)

        assert result.total_expire == 0
        assert result.total_a_renouveler == 0
        assert result.total_a_renseigner == 0
        assert result.total_valide == 0

    @patch("app.modules.dashboard.application.service.get_dashboard_repository")
    @patch("app.modules.dashboard.application.service.get_residence_permit_calculator")
    def test_exception_returns_zeros(self, mock_get_calc, mock_get_repo):
        """En cas d'exception, retourne des zéros (comportement défensif)."""
        mock_repo = MagicMock()
        mock_repo.get_employees_for_residence_permit_stats.side_effect = RuntimeError(
            "DB error"
        )
        mock_get_repo.return_value = mock_repo

        result = get_residence_permit_stats(COMPANY_ID)

        assert result.total_expire == 0
        assert result.total_a_renouveler == 0
        assert result.total_a_renseigner == 0
        assert result.total_valide == 0


class TestBuildFullDashboard:
    """Tests de build_full_dashboard (service)."""

    @patch("app.modules.dashboard.application.service.get_dashboard_repository")
    def test_returns_dashboard_data_structure(self, mock_get_repo):
        """build_full_dashboard retourne un DashboardData avec tous les champs."""
        mock_repo = MagicMock()
        mock_repo.get_employees_for_dashboard.return_value = [
            {
                "id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "hire_date": "2020-01-15",
                "date_naissance": "1990-05-10",
                "contract_type": "CDI",
            },
        ]
        mock_repo.get_pending_absence_requests_count.return_value = 2
        mock_repo.get_pending_expense_reports_count.return_value = 1
        mock_repo.get_absence_requests_validated_today.return_value = []
        mock_repo.get_payslips_by_company.return_value = []
        mock_repo.get_absence_requests_for_absenteeism.return_value = []
        mock_get_repo.return_value = mock_repo

        result = build_full_dashboard(COMPANY_ID)

        assert isinstance(result, DashboardData)
        assert result.kpis.effectifActif == 1
        assert result.kpis.cdiCount == 1
        assert result.kpis.cddCount == 0
        assert result.actions.pendingAbsences == 2
        assert result.actions.pendingExpenses == 1
        assert len(result.employees) == 1
        assert result.employees[0].first_name == "Jean"
        assert result.employees[0].last_name == "Dupont"
        assert result.teamPulse.absentToday == []
        mock_repo.get_employees_for_dashboard.assert_called_once_with(COMPANY_ID)

    @patch("app.modules.dashboard.application.service.get_dashboard_repository")
    def test_contract_distribution_in_kpis(self, mock_get_repo):
        """La répartition des contrats (CDI/CDD) est dans kpis.contractDistribution."""
        mock_repo = MagicMock()
        mock_repo.get_employees_for_dashboard.return_value = [
            {"id": "1", "first_name": "A", "last_name": "A", "contract_type": "CDI"},
            {"id": "2", "first_name": "B", "last_name": "B", "contract_type": "CDD"},
            {"id": "3", "first_name": "C", "last_name": "C", "contract_type": "CDI"},
        ]
        mock_repo.get_pending_absence_requests_count.return_value = 0
        mock_repo.get_pending_expense_reports_count.return_value = 0
        mock_repo.get_absence_requests_validated_today.return_value = []
        mock_repo.get_payslips_by_company.return_value = []
        mock_repo.get_absence_requests_for_absenteeism.return_value = []
        mock_get_repo.return_value = mock_repo

        result = build_full_dashboard(COMPANY_ID)

        assert result.kpis.contractDistribution.get("CDI") == 2
        assert result.kpis.contractDistribution.get("CDD") == 1
        assert result.kpis.cdiCount == 2
        assert result.kpis.cddCount == 1
