"""Tests service comptabilisation pointages."""

from unittest.mock import MagicMock, patch

from app.modules.schedules.application.punch_accounting_service import (
    inject_approved_punch_overtime_into_calendar,
)


@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
@patch(
    "app.modules.schedules.application.punch_accounting_service.repo.list_approved_overtime_for_month"
)
def test_inject_approved_punch_overtime_adds_hs25(mock_list_approved, mock_settings):
    mock_settings.return_value = MagicMock(enabled=True)
    mock_list_approved.return_value = [
        {"employee_id": "emp-1", "overtime_hours": 1.5},
        {"employee_id": "emp-1", "overtime_hours": 0.5},
    ]

    calendrier = [{"type": "travail", "heures": 151.0}]
    result = inject_approved_punch_overtime_into_calendar(
        calendrier,
        company_id="co-1",
        employee_id="emp-1",
        year=2026,
        month=6,
    )

    hs = next(e for e in result if e["type"] == "travail_hs25")
    assert hs["heures"] == 2.0
    assert result[0]["heures"] == 151.0


@patch("app.modules.schedules.application.punch_accounting_service.repo.get_settings")
def test_inject_skipped_when_disabled(mock_settings):
    mock_settings.return_value = MagicMock(enabled=False)
    calendrier = [{"type": "travail", "heures": 151.0}]
    assert (
        inject_approved_punch_overtime_into_calendar(
            calendrier, "co-1", "emp-1", 2026, 6
        )
        == calendrier
    )
