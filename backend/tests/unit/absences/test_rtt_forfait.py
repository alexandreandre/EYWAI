"""Tests RTT forfait jours cadres."""

from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.rtt_forfait import calculate_rtt_annual_forfait_jours
from app.modules.absences.domain.rules import resolve_rtt_annual_base


def test_rtt_forfait_2026_cartol_defaults():
    """Forfait 214, CP 25, fériés légaux → 13 j en 2026."""
    result = calculate_rtt_annual_forfait_jours(
        2026,
        forfait_days=214,
        cp_ouvres_deduction=25.0,
        observed_holiday_ids=None,
    )
    assert result == 13.0


def test_resolve_rtt_default_unchanged():
    policy = LeavePolicySettings()
    assert resolve_rtt_annual_base(2025, policy) == 10.0


def test_resolve_rtt_fixed_priority():
    policy = LeavePolicySettings(rtt_annual_days=12.0)
    assert resolve_rtt_annual_base(2026, policy) == 12.0


def test_resolve_rtt_forfait_mode():
    policy = LeavePolicySettings(
        rtt_use_forfait_jours_formula=True,
        rtt_forfait_annual_days=214,
        rtt_forfait_cp_ouvres_deduction=25.0,
    )
    assert resolve_rtt_annual_base(2026, policy) == 13.0


def test_resolve_rtt_calendar_still_works():
    policy = LeavePolicySettings(rtt_use_calendar_formula=True)
    assert resolve_rtt_annual_base(2025, policy) == 10.0
    assert resolve_rtt_annual_base(2024, policy) == 11.0
