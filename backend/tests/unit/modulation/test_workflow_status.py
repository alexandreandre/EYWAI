"""Tests indicateurs workflow modulation."""

from unittest.mock import patch

from app.modules.modulation.infrastructure import repository as repo


@patch("app.modules.modulation.infrastructure.repository.list_employee_counters")
@patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
def test_count_employees_over_balance_cap(mock_settings, mock_counters):
    mock_settings.return_value = type(
        "S",
        (),
        {
            "hour_account_enabled": True,
            "max_account_balance_hours": 50.0,
        },
    )()
    mock_counters.return_value = [
        {"account_balance_hours": 40},
        {"account_balance_hours": 55},
        {"account_balance_hours": 50},
    ]
    assert repo.count_employees_over_balance_cap("company-1", 2026) == 1


@patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
def test_count_employees_over_balance_cap_no_max(mock_settings):
    mock_settings.return_value = type(
        "S",
        (),
        {"hour_account_enabled": True, "max_account_balance_hours": None},
    )()
    assert repo.count_employees_over_balance_cap("company-1", 2026) == 0
