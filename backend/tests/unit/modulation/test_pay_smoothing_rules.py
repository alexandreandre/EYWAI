"""Tests lissage paie modulation."""

from datetime import date

from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.pay_smoothing_rules import (
    compute_smoothing_gain_for_month,
    count_low_weeks_in_month,
)


def test_count_low_weeks_march_2026_alternating():
    settings = ModulationSettings(
        enabled=True,
        weekly_high_hours=37,
        weekly_low_hours=32,
        high_weeks_per_cycle=1,
        low_weeks_per_cycle=1,
        cycle_start_week_iso=date(2026, 1, 5),
    )
    low_weeks = count_low_weeks_in_month(settings, 2026, 3)
    assert low_weeks >= 1


def test_smoothing_gain_zero_when_disabled():
    settings = ModulationSettings(enabled=False, pay_smoothed=True)
    assert compute_smoothing_gain_for_month(settings, 2026, 3, 20.0) == 0.0


def test_smoothing_gain_on_low_weeks():
    settings = ModulationSettings(
        enabled=True,
        pay_smoothed=True,
        average_weekly_hours=35,
        weekly_low_hours=32,
        high_weeks_per_cycle=1,
        low_weeks_per_cycle=1,
        cycle_start_week_iso=date(2026, 1, 5),
    )
    low_weeks = count_low_weeks_in_month(settings, 2026, 3)
    gain = compute_smoothing_gain_for_month(settings, 2026, 3, 20.0)
    expected = round(low_weeks * (35 - 32) * 20.0, 2)
    assert gain == expected
    assert gain > 0
