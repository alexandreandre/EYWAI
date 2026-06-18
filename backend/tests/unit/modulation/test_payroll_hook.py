"""Tests modulation payroll hook."""

from datetime import date

from app.modules.modulation.application.payroll_hook import (
    build_modulation_weekly_hours_map,
    week_config_from_template,
)
from app.modules.modulation.domain.entities import ModulationSettings


def test_build_weekly_hours_map_alternating():
    settings = ModulationSettings(
        enabled=True,
        weekly_high_hours=37,
        weekly_low_hours=32,
        high_weeks_per_cycle=1,
        low_weeks_per_cycle=1,
        cycle_start_week_iso=date(2026, 1, 5),
    )
    m = build_modulation_weekly_hours_map(settings, 2026)
    w1 = date(2026, 1, 5).isocalendar()[:2]
    w2 = date(2026, 1, 12).isocalendar()[:2]
    assert m[w1] == 37.0
    assert m[w2] == 32.0


def test_week_config_from_template():
    cfg = week_config_from_template(
        [
            {"day": 1, "hours": 7.5, "type": "travail"},
            {"day": 2, "hours": 7.5, "type": "travail"},
        ]
    )
    assert cfg["monday"]["hours"] == 7.5
    assert cfg["monday"]["type"] == "travail"
