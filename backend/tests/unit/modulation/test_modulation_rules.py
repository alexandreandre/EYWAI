"""Tests modulation — cycle semaines high/low."""

from datetime import date

from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.domain.rules import (
    compute_balance_hours,
    resolve_modulation_tier,
    theoretical_weekly_hours,
)


def _settings_enabled() -> ModulationSettings:
    return ModulationSettings(
        enabled=True,
        weekly_high_hours=37.0,
        weekly_low_hours=32.0,
        high_weeks_per_cycle=1,
        low_weeks_per_cycle=1,
        cycle_start_week_iso=date(2026, 1, 5),
    )


def test_alternating_high_low_weeks():
    settings = _settings_enabled()
    w1 = date(2026, 1, 5)
    w2 = date(2026, 1, 12)
    assert resolve_modulation_tier(w1, settings) == "high"
    assert resolve_modulation_tier(w2, settings) == "low"
    assert theoretical_weekly_hours("high", settings) == 37.0
    assert theoretical_weekly_hours("low", settings) == 32.0


def test_annual_balance_near_zero_for_alternating_cycle():
    """37h + 32h sur 26 semaines chacune → solde cumulé ≈ 0 si réel = théorique."""
    settings = _settings_enabled()
    balance = 0.0
    start = date(2026, 1, 5)
    for i in range(52):
        week = date.fromordinal(start.toordinal() + i * 7)
        tier = resolve_modulation_tier(week, settings)
        theoretical = theoretical_weekly_hours(tier, settings)
        balance += compute_balance_hours(theoretical, theoretical)
    assert abs(balance) < 0.01


def test_balance_positive_when_overtime():
    _settings_enabled()
    assert compute_balance_hours(32.0, 40.0) == 8.0
