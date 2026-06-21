"""Tests métriques paie par poste (nuit, pause payée)."""

from app.modules.planning.domain.shift_payroll_metrics import (
    compute_night_hours,
    compute_paid_break_hours,
)

NIGHT_WINDOWS = [
    {"start": "22:00", "end": "06:00", "rate": 0.5},
    {"start": "05:00", "end": "06:00", "rate": 0.5},
]


def test_morning_shift_one_night_hour():
    result = compute_night_hours("05:00", "13:00", NIGHT_WINDOWS)
    assert result.hours == 1.0
    assert result.average_rate == 0.5


def test_afternoon_shift_no_night():
    result = compute_night_hours("13:00", "21:00", NIGHT_WINDOWS)
    assert result.hours == 0.0


def test_overnight_shift_eight_night_hours():
    result = compute_night_hours("22:00", "06:00", NIGHT_WINDOWS)
    assert result.hours == 8.0
    assert result.average_rate == 0.5


def test_paid_break_thirty_minutes():
    assert compute_paid_break_hours(30) == 0.5


def test_paid_break_zero():
    assert compute_paid_break_hours(0) == 0.0
    assert compute_paid_break_hours(None) == 0.0


def test_no_night_windows():
    result = compute_night_hours("22:00", "06:00", None)
    assert result.hours == 0.0
