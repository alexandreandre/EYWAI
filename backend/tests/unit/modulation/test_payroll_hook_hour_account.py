"""Tests hook paie compte d'heures modulation."""

from unittest.mock import patch

from app.modules.modulation.application.payroll_hook import (
    apply_modulation_hour_account_to_calendar,
)
from app.modules.modulation.domain.entities import ModulationSettings


def _hs_calendar(*hours: float) -> list[dict]:
    return [{"type": "travail_hs25", "heures": h} for h in hours]


@patch("app.modules.modulation.application.payroll_hook.sync_employee_modulation_counter")
@patch("app.modules.modulation.application.payroll_hook.sync_account_balance_cache")
@patch("app.modules.modulation.application.payroll_hook.repo.insert_movement")
@patch("app.modules.modulation.application.payroll_hook.repo.get_franchise_consumed_in_period")
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee_year")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_apply_hour_account_franchise_14_of_20(
    mock_settings,
    mock_movements,
    mock_consumed,
    mock_insert,
    _mock_sync_cache,
    _mock_sync_counter,
):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True,
        hs_franchise_hours_per_period=14,
    )
    mock_movements.return_value = []
    mock_consumed.return_value = 0.0
    mock_insert.return_value = {"id": "mov-1"}

    calendar = _hs_calendar(12, 8)
    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1",
        "emp-1",
        2026,
        3,
        calendar,
    )

    assert result.hs_realisees == 20.0
    assert result.hs_credited == 14.0
    assert result.hs_paid == 6.0
    assert movement_ids == ["mov-1"]
    mock_insert.assert_called_once()
    paid_hs = sum(
        float(j.get("heures") or 0)
        for j in updated
        if j.get("type") in ("travail_hs25", "travail_hs50")
    )
    assert paid_hs == 6.0


@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_apply_hour_account_disabled_returns_unchanged(mock_settings):
    mock_settings.return_value = ModulationSettings(hour_account_enabled=False)
    calendar = _hs_calendar(10)

    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1",
        "emp-1",
        2026,
        3,
        calendar,
    )

    assert updated == calendar
    assert movement_ids == []
    assert result.hs_credited == 0.0
