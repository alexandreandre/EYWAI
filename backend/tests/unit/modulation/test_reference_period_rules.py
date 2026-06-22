"""Tests périodes de référence horaire."""

from datetime import date

from app.modules.modulation.domain.reference_period_rules import (
    WorkTimePeriod,
    build_effective_weekly_hours_map,
    period_weekly_hours,
    resolve_effective_weekly_hours_for_week,
    validate_no_overlap,
)


def _period(
    label: str,
    start: str,
    end: str | None,
    daily: float | None = None,
    weekly: float | None = None,
) -> WorkTimePeriod:
    return WorkTimePeriod(
        id="p1",
        company_id="c1",
        label=label,
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end) if end else None,
        daily_reference_hours=daily,
        weekly_reference_hours=weekly,
        affects_payroll=True,
        affects_planning=False,
        default_week_template_id=None,
        is_active=True,
    )


def test_period_weekly_from_daily():
    p = _period("ap", "2026-01-01", None, daily=7.0)
    assert period_weekly_hours(p) == 35.0


def test_resolve_period_over_modulation():
    monday = date(2026, 6, 1)
    periods = [_period("ap", "2026-01-01", "2026-12-31", daily=7.0)]
    mod_map = {(2026, 23): 37.0}
    assert resolve_effective_weekly_hours_for_week(35.0, monday, mod_map, periods) == 35.0


def test_resolve_modulation_when_no_period():
    monday = date(2026, 6, 1)
    mod_map = {(monday.isocalendar()[0], monday.isocalendar()[1]): 32.0}
    assert resolve_effective_weekly_hours_for_week(35.0, monday, mod_map, []) == 32.0


def test_validate_overlap_raises():
    existing = [_period("a", "2026-01-01", "2026-06-30", daily=7)]
    candidate = _period("b", "2026-03-01", None, daily=7.75)
    candidate = WorkTimePeriod(
        id="p2",
        company_id="c1",
        label="b",
        start_date=date(2026, 3, 1),
        end_date=None,
        daily_reference_hours=7.75,
        weekly_reference_hours=None,
        affects_payroll=True,
        affects_planning=False,
        default_week_template_id=None,
        is_active=True,
    )
    try:
        validate_no_overlap(existing, candidate)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_map_uses_period():
    periods = [_period("ap", "2026-01-01", "2026-12-31", weekly=28.0)]
    m = build_effective_weekly_hours_map(2026, 35.0, None, periods)
    june_key = date(2026, 6, 15).isocalendar()[:2]
    assert m[june_key] == 28.0
