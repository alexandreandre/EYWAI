"""Tests majorations astreinte week-end."""

from datetime import date

from app.modules.payroll_variables.domain.astreinte_weekend_majoration import (
    evaluate_astreinte_weekend_majoration,
)


def test_saturday_one_hour_eligible():
    rule = {
        "code": "astreinte_sat",
        "conditions": {"weekday_rates": {"5": 0.25, "6": 1.0}, "min_hours": 1.0},
    }
    calendrier = [{"jour": 7, "heures_faites": 2.0}]
    astreinte = [date(2026, 3, 7)]
    results = evaluate_astreinte_weekend_majoration(
        rule,
        year=2026,
        month=3,
        calendrier_reel=calendrier,
        astreinte_shift_dates=astreinte,
        hourly_rate=20.0,
    )
    assert len(results) == 1
    assert results[0]["amount"] == 5.0
    assert results[0]["weekday"] == 5


def test_below_min_hours_skipped():
    rule = {"code": "astreinte_sat", "conditions": {"min_hours": 1.0}}
    calendrier = [{"jour": 7, "heures_faites": 0.5}]
    results = evaluate_astreinte_weekend_majoration(
        rule,
        year=2026,
        month=3,
        calendrier_reel=calendrier,
        astreinte_shift_dates=[date(2026, 3, 7)],
        hourly_rate=20.0,
    )
    assert results == []


def test_no_astreinte_same_week_skipped():
    rule = {"code": "astreinte_sat", "conditions": {}}
    calendrier = [{"jour": 7, "heures_faites": 3.0}]
    results = evaluate_astreinte_weekend_majoration(
        rule,
        year=2026,
        month=3,
        calendrier_reel=calendrier,
        astreinte_shift_dates=[date(2026, 3, 1)],
        hourly_rate=20.0,
    )
    assert results == []


def test_sunday_full_majoration():
    rule = {"code": "astreinte_sun", "conditions": {}}
    calendrier = [{"jour": 8, "heures_faites": 1.5}]
    results = evaluate_astreinte_weekend_majoration(
        rule,
        year=2026,
        month=3,
        calendrier_reel=calendrier,
        astreinte_shift_dates=[date(2026, 3, 8)],
        hourly_rate=10.0,
    )
    assert len(results) == 1
    assert results[0]["amount"] == 10.0
    assert results[0]["weekday"] == 6
