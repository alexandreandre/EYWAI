"""Scénarios profils entreprise — modulation / compte HS."""

from unittest.mock import patch

from app.modules.modulation.application.payroll_hook import (
    apply_modulation_hour_account_to_calendar,
)
from app.modules.modulation.domain.entities import ModulationSettings


@patch("app.modules.modulation.application.payroll_hook.sync_employee_modulation_counter")
@patch("app.modules.modulation.application.payroll_hook.sync_account_balance_cache")
@patch("app.modules.modulation.application.payroll_hook.repo.insert_movement")
@patch("app.modules.modulation.application.payroll_hook.repo.get_franchise_consumed_in_period")
@patch("app.modules.modulation.application.payroll_hook.repo.list_movements_for_employee_year")
@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_hour_account_only_no_modulation(
    mock_settings,
    mock_movements,
    mock_consumed,
    mock_insert,
    _mock_sync_cache,
    _mock_sync_counter,
):
    """Profil compte HS sans accord : enabled=false, account_all."""
    mock_settings.return_value = ModulationSettings(
        enabled=False,
        hour_account_enabled=True,
        hs_routing_policy="account_all",
    )
    mock_movements.return_value = []
    mock_consumed.return_value = 0.0
    mock_insert.return_value = {"id": "mov-1"}

    calendar = [{"type": "travail_hs25", "heures": 6.0}]
    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 3, calendar
    )

    assert result.hs_credited == 6.0
    assert result.hs_paid == 0.0
    paid_hs = sum(
        float(j.get("heures") or 0)
        for j in updated
        if j.get("type") in ("travail_hs25", "travail_hs50")
    )
    assert paid_hs == 0.0


@patch("app.modules.modulation.application.payroll_hook.repo.get_modulation_settings")
def test_pay_all_skips_account(mock_settings):
    mock_settings.return_value = ModulationSettings(
        hour_account_enabled=True,
        hs_routing_policy="pay_all",
    )
    calendar = [{"type": "travail_hs25", "heures": 5.0}]
    updated, movement_ids, result = apply_modulation_hour_account_to_calendar(
        "company-1", "emp-1", 2026, 3, calendar
    )
    assert updated == calendar
    assert movement_ids == []
    assert result.hs_credited == 0.0
