"""
Tests d'intégration du repository dashboard : DashboardRepository.

Vérifie que chaque méthode délègue aux bonnes fonctions infrastructure.queries
et retourne le type attendu. Avec mocks Supabase (pas de DB réelle requise).
Pour tests contre une DB de test : utiliser la fixture db_session (à compléter
dans conftest.py) et des données dans employees, absence_requests, payslips,
expense_reports.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.dashboard.infrastructure.repository import DashboardRepository


pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestDashboardRepository:
    """DashboardRepository : délégation vers infrastructure.queries."""

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_employees_for_dashboard_calls_fetch(self, mock_queries):
        """get_employees_for_dashboard appelle fetch_employees_for_dashboard."""
        mock_queries.fetch_employees_for_dashboard.return_value = [
            {"id": "e1", "first_name": "Jean", "last_name": "Dupont"},
        ]
        repo = DashboardRepository()
        result = repo.get_employees_for_dashboard(COMPANY_ID)
        mock_queries.fetch_employees_for_dashboard.assert_called_once_with(COMPANY_ID)
        assert len(result) == 1
        assert result[0]["id"] == "e1"

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_absence_requests_validated_today(self, mock_queries):
        """get_absence_requests_validated_today appelle fetch avec today_iso."""
        mock_queries.fetch_absences_validated_today.return_value = []
        repo = DashboardRepository()
        result = repo.get_absence_requests_validated_today(COMPANY_ID)
        today_iso = date.today().isoformat()
        mock_queries.fetch_absences_validated_today.assert_called_once_with(
            COMPANY_ID, today_iso
        )
        assert result == []

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_absence_requests_for_absenteeism(self, mock_queries):
        """get_absence_requests_for_absenteeism délègue à fetch."""
        mock_queries.fetch_absence_requests_for_absenteeism.return_value = [
            {"employee_id": "e1", "selected_days": ["2025-03-10"]},
        ]
        repo = DashboardRepository()
        result = repo.get_absence_requests_for_absenteeism(COMPANY_ID)
        mock_queries.fetch_absence_requests_for_absenteeism.assert_called_once_with(
            COMPANY_ID
        )
        assert len(result) == 1
        assert result[0]["employee_id"] == "e1"

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_payslips_by_company(self, mock_queries):
        """get_payslips_by_company délègue à fetch_payslips_by_company."""
        mock_queries.fetch_payslips_by_company.return_value = [
            {"month": 2, "payslip_data": {"net_a_payer": 2000}},
        ]
        repo = DashboardRepository()
        result = repo.get_payslips_by_company(COMPANY_ID)
        mock_queries.fetch_payslips_by_company.assert_called_once_with(COMPANY_ID)
        assert len(result) == 1
        assert result[0]["month"] == 2

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_pending_expense_reports_count(self, mock_queries):
        """get_pending_expense_reports_count retourne un int."""
        mock_queries.get_pending_expense_reports_count.return_value = 3
        repo = DashboardRepository()
        result = repo.get_pending_expense_reports_count(COMPANY_ID)
        mock_queries.get_pending_expense_reports_count.assert_called_once_with(
            COMPANY_ID
        )
        assert result == 3

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_pending_absence_requests_count(self, mock_queries):
        """get_pending_absence_requests_count retourne un int."""
        mock_queries.get_pending_absence_requests_count.return_value = 2
        repo = DashboardRepository()
        result = repo.get_pending_absence_requests_count(COMPANY_ID)
        mock_queries.get_pending_absence_requests_count.assert_called_once_with(
            COMPANY_ID
        )
        assert result == 2

    @patch("app.modules.dashboard.infrastructure.repository.queries")
    def test_get_employees_for_residence_permit_stats(self, mock_queries):
        """get_employees_for_residence_permit_stats délègue à fetch."""
        mock_queries.fetch_employees_for_residence_permit_stats.return_value = [
            {
                "id": "e1",
                "is_subject_to_residence_permit": True,
                "residence_permit_expiry_date": "2026-06-01",
                "employment_status": "actif",
            },
        ]
        repo = DashboardRepository()
        result = repo.get_employees_for_residence_permit_stats(COMPANY_ID)
        mock_queries.fetch_employees_for_residence_permit_stats.assert_called_once_with(
            COMPANY_ID
        )
        assert len(result) == 1
        assert result[0]["employment_status"] == "actif"


class TestGetDashboardRepository:
    """get_dashboard_repository() retourne une instance IDashboardDataReader."""

    def test_returns_repository_instance(self):
        """get_dashboard_repository retourne un objet avec les méthodes du port."""
        from app.modules.dashboard.infrastructure.repository import get_dashboard_repository
        repo = get_dashboard_repository()
        assert hasattr(repo, "get_employees_for_dashboard")
        assert hasattr(repo, "get_absence_requests_validated_today")
        assert hasattr(repo, "get_absence_requests_for_absenteeism")
        assert hasattr(repo, "get_payslips_by_company")
        assert hasattr(repo, "get_pending_expense_reports_count")
        assert hasattr(repo, "get_pending_absence_requests_count")
        assert hasattr(repo, "get_employees_for_residence_permit_stats")
