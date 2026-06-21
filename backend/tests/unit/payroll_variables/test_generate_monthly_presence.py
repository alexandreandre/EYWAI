"""Tests génération mensuelle — règle per_week_without_absence."""

from unittest.mock import MagicMock, patch

from app.modules.payroll_variables.application.generate_monthly import (
    generate_monthly_variables,
)
from app.modules.payroll_variables.domain.presence_week import iso_week_mondays_in_month


def _employees_table_mock(rows: list[dict]) -> MagicMock:
    execute_result = MagicMock(data=rows)
    chain = MagicMock()
    chain.execute.return_value = execute_result
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.select.return_value = chain
    table = MagicMock()
    table.select.return_value = chain
    return table


@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_locked_shift_dates_for_employee"
)
@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_validated_absences_for_employees_in_range"
)
@patch("app.modules.payroll_variables.application.generate_monthly.supabase")
@patch("app.modules.payroll_variables.application.generate_monthly.repo")
def test_dry_run_presence_all_weeks_eligible(
    mock_repo, mock_supabase, mock_absences, mock_shifts
):
    mock_repo.list_rules.return_value = [
        {
            "enabled": True,
            "rule_type": "per_week_without_absence",
            "code": "presence",
            "label": "Prime présence",
            "amount": 6.0,
            "generation_mode": "auto",
            "conditions": {
                "amount_per_week": 6.0,
                "absence_types": ["maladie"],
            },
        }
    ]
    mock_repo.list_special_days.return_value = []
    mock_supabase.table.return_value = _employees_table_mock(
        [{"id": "emp-1", "first_name": "Alice", "last_name": "Test", "statut": "cadre"}]
    )
    mock_absences.return_value = []
    mock_shifts.return_value = []

    result = generate_monthly_variables("company-1", 2026, 6, dry_run=True)

    expected_weeks = len(iso_week_mondays_in_month(2026, 6))
    assert result["dry_run"] is True
    assert len(result["preview"]) == 1
    assert result["preview"][0]["quantity"] == float(expected_weeks)
    assert result["preview"][0]["amount"] == round(expected_weeks * 6.0, 2)
    assert result["written_count"] == 0
    mock_repo.upsert_monthly_input.assert_not_called()


@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_locked_shift_dates_for_employee"
)
@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_validated_absences_for_employees_in_range"
)
@patch("app.modules.payroll_variables.application.generate_monthly.supabase")
@patch("app.modules.payroll_variables.application.generate_monthly.repo")
def test_dry_run_presence_absence_reduces_weeks(
    mock_repo, mock_supabase, mock_absences, mock_shifts
):
    mock_repo.list_rules.return_value = [
        {
            "enabled": True,
            "rule_type": "per_week_without_absence",
            "code": "presence",
            "label": "Prime présence",
            "amount": 6.0,
            "generation_mode": "auto",
            "conditions": {
                "amount_per_week": 6.0,
                "absence_types": ["maladie"],
            },
        }
    ]
    mock_repo.list_special_days.return_value = []
    mock_supabase.table.return_value = _employees_table_mock(
        [{"id": "emp-1", "first_name": "Alice", "last_name": "Test", "statut": "cadre"}]
    )
    mock_absences.return_value = [
        {
            "employee_id": "emp-1",
            "type": "maladie",
            "status": "validated",
            "selected_days": ["2026-06-10"],
        }
    ]
    mock_shifts.return_value = []

    result = generate_monthly_variables("company-1", 2026, 6, dry_run=True)

    full = len(iso_week_mondays_in_month(2026, 6))
    assert len(result["preview"]) == 1
    assert result["preview"][0]["quantity"] < float(full)
    mock_repo.upsert_monthly_input.assert_not_called()


@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_locked_shift_dates_for_employee"
)
@patch(
    "app.modules.payroll_variables.application.generate_monthly.list_validated_absences_for_employees_in_range"
)
@patch("app.modules.payroll_variables.application.generate_monthly.supabase")
@patch("app.modules.payroll_variables.application.generate_monthly.repo")
def test_dry_run_presence_export_code_from_conditions(
    mock_repo, mock_supabase, mock_absences, mock_shifts
):
    mock_repo.list_rules.return_value = [
        {
            "enabled": True,
            "rule_type": "per_week_without_absence",
            "code": "presence",
            "label": "Prime présence",
            "amount": 6.0,
            "generation_mode": "auto",
            "conditions": {
                "amount_per_week": 6.0,
                "absence_types": ["maladie"],
                "export_code": "SPEQ",
            },
        }
    ]
    mock_repo.list_special_days.return_value = []
    mock_supabase.table.return_value = _employees_table_mock(
        [{"id": "emp-1", "first_name": "Alice", "last_name": "Test", "statut": "cadre"}]
    )
    mock_absences.return_value = []
    mock_shifts.return_value = []

    generate_monthly_variables("company-1", 2026, 6, dry_run=False)

    mock_repo.upsert_monthly_input.assert_called_once()
    payload = mock_repo.upsert_monthly_input.call_args[0][0]
    assert payload["export_code"] == "SPEQ"
