"""Tests politique de pauses multi-types."""

from app.modules.schedules.domain.break_policy import (
    INDUSTRIAL_2X10_MEAL_30,
    compute_break_totals,
    enrich_day_config_breaks,
    resolve_breaks,
)
from app.modules.schedules.domain.calendar_generation_rules import (
    build_month_calendrier_prevu,
    day_config_map,
    normalize_day_config,
)


def test_industrial_break_totals():
    total, paid, unpaid = compute_break_totals(INDUSTRIAL_2X10_MEAL_30)
    assert total == 50
    assert paid == 20
    assert unpaid == 30


def test_normalize_day_config_from_breaks_array():
    cfg = normalize_day_config(
        {
            "day": 1,
            "hours": 7.5,
            "start": "08:00",
            "end": "16:00",
            "breaks": [dict(b) for b in INDUSTRIAL_2X10_MEAL_30],
        }
    )
    assert cfg["paid_break_minutes"] == 20
    assert cfg["unpaid_break_minutes"] == 30
    assert cfg["break_minutes"] == 50
    assert cfg["break_paid"] is False


def test_calendrier_prevu_propagates_unpaid_break():
    days = [
        normalize_day_config(
            {
                "day": d,
                "hours": 7.5,
                "breaks": [dict(b) for b in INDUSTRIAL_2X10_MEAL_30],
            }
        )
        for d in [1, 2, 3, 4, 5]
    ]
    dm = day_config_map(days)
    entries = build_month_calendrier_prevu(2026, 8, lambda _m: dm)
    worked = [e for e in entries if e.get("heures_prevues") == 7.5]
    assert len(worked) >= 20
    sample = worked[0]
    assert sample.get("unpaid_break_minutes") == 30
    assert sample.get("paid_break_minutes") == 20
    assert sample.get("pause_min") == 30
    assert sample.get("pause_payee") is False


def test_legacy_break_minutes_still_works():
    cfg = enrich_day_config_breaks(
        {"day": 1, "hours": 7.5, "break_minutes": 30, "break_paid": False}
    )
    assert cfg["unpaid_break_minutes"] == 30
    assert cfg["paid_break_minutes"] == 0
    assert len(resolve_breaks(cfg)) == 1
