"""Tests unitaires — clôture RTT fin d'année (overview RH)."""

from datetime import date
from unittest.mock import patch

from app.modules.absences.application.leave_settings_queries import (
    get_rtt_year_end_overview,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)


class TestGetRttYearEndOverview:
    @patch(
        "app.modules.absences.application.leave_settings_queries.should_show_rtt_year_end_reminder",
        return_value=False,
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_adjustments_by_employees_year",
        return_value={},
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.absence_repository"
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_employees_hire_dates_batch",
        return_value={"emp-forfait": "2020-01-01", "emp-non-forfait": "2020-01-01"},
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries._list_active_employees"
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_leave_policy"
    )
    def test_includes_forfait_cadre_with_forfait_formula_policy(
        self,
        mock_get_policy,
        mock_list_employees,
        _mock_hire_dates,
        mock_absence_repo,
        _mock_adjustments,
        _mock_reminder,
    ):
        mock_get_policy.return_value = LeavePolicySettings(
            rtt_use_forfait_jours_formula=True,
            rtt_forfait_cadres_only=True,
        )
        mock_list_employees.return_value = [
            {
                "id": "emp-forfait",
                "first_name": "Elsa",
                "last_name": "ANDRE",
                "statut": "Cadre forfait jour",
                "hire_date": "2020-01-01",
                "prior_service_months": 0,
                "specificites_paie": {},
            },
            {
                "id": "emp-non-forfait",
                "first_name": "Jean",
                "last_name": "DUPONT",
                "statut": "Employé",
                "hire_date": "2020-01-01",
                "prior_service_months": 0,
                "specificites_paie": {},
            },
        ]
        mock_absence_repo.list_validated_for_employees.return_value = []

        result = get_rtt_year_end_overview("co-1", year=2026)

        assert result.year == 2026
        assert len(result.employees) == 1
        assert result.employees[0].employee_id == "emp-forfait"
        assert result.employees[0].first_name == "Elsa"
        assert result.employees[0].last_name == "ANDRE"
        assert result.employees[0].rtt_remaining > 0
        assert result.employees[0].closure_required is True

    @patch(
        "app.modules.absences.application.leave_settings_queries.should_show_rtt_year_end_reminder",
        return_value=False,
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_adjustments_by_employees_year"
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.absence_repository"
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_employees_hire_dates_batch",
        return_value={"emp-forfait": "2020-01-01"},
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries._list_active_employees"
    )
    @patch(
        "app.modules.absences.application.leave_settings_queries.get_leave_policy"
    )
    def test_keeps_already_closed_employee_with_positive_remaining(
        self,
        mock_get_policy,
        mock_list_employees,
        _mock_hire_dates,
        mock_absence_repo,
        mock_adjustments,
        _mock_reminder,
    ):
        mock_get_policy.return_value = LeavePolicySettings(
            rtt_use_forfait_jours_formula=True,
            rtt_forfait_cadres_only=True,
        )
        mock_list_employees.return_value = [
            {
                "id": "emp-forfait",
                "first_name": "Elsa",
                "last_name": "ANDRE",
                "statut": "Cadre forfait jour",
                "hire_date": "2020-01-01",
                "prior_service_months": 0,
                "specificites_paie": {},
            },
        ]
        mock_absence_repo.list_validated_for_employees.return_value = []
        mock_adjustments.return_value = {
            "emp-forfait": EmployeeLeaveAdjustment(
                rtt_forfeited_at="2026-12-15T00:00:00Z",
                rtt_forfeited_days=5.0,
            )
        }

        result = get_rtt_year_end_overview("co-1", year=2026)

        assert len(result.employees) == 1
        assert result.employees[0].already_closed is True
        assert result.employees[0].closure_required is False
