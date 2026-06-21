"""Tests domaine prime astreinte hebdomadaire."""

from datetime import date

from app.modules.payroll_variables.domain.astreinte_week import (
    compute_week_payouts,
    evaluate_astreinte_week_tiered,
    is_christmas_week,
)


def test_normal_week_amount():
    monday = date(2026, 3, 2)
    lines = compute_week_payouts(
        monday,
        [date(2026, 3, 5)],
        [],
        [],
        {"amount_normal": 176.18},
        year=2026,
    )
    assert len(lines) == 1
    assert lines[0]["amount"] == 176.18
    assert lines[0]["kind"] == "week_normal"


def test_christmas_week_replace():
    monday = date(2025, 12, 22)
    assert is_christmas_week(
        monday, detection="iso_dec_25", special_days=[], year=2025
    )
    lines = compute_week_payouts(
        monday,
        [date(2025, 12, 24)],
        [],
        [],
        {
            "amount_normal": 176.18,
            "amount_christmas": 352.36,
            "christmas_mode": "replace",
        },
        year=2025,
    )
    assert lines[0]["amount"] == 352.36
    assert lines[0]["kind"] == "week_christmas_replace"


def test_christmas_week_add():
    monday = date(2025, 12, 22)
    lines = compute_week_payouts(
        monday,
        [date(2025, 12, 24)],
        [],
        [],
        {
            "amount_normal": 176.18,
            "amount_christmas": 352.36,
            "christmas_mode": "add",
        },
        year=2025,
    )
    assert lines[0]["amount"] == round(176.18 + 352.36, 2)


def test_bridge_add():
    monday = date(2026, 5, 4)
    bridge = date(2026, 5, 8)
    lines = compute_week_payouts(
        monday,
        [bridge],
        [bridge],
        [],
        {"amount_normal": 176.18, "amount_bridge": 250.0, "bridge_mode": "add"},
        year=2026,
    )
    assert len(lines) == 2
    assert lines[0]["amount"] == 176.18
    assert lines[1]["amount"] == 250.0
    assert lines[1]["kind"] == "week_bridge_add"


def test_evaluate_filters_by_month():
    rule = {
        "code": "astreinte_week",
        "conditions": {"amount_normal": 176.18},
    }
    shift_dates = [date(2026, 3, 7)]
    results = evaluate_astreinte_week_tiered(
        rule,
        year=2026,
        month=3,
        shift_dates=shift_dates,
        special_days=[],
    )
    assert len(results) == 1
    assert results[0]["amount"] == 176.18
