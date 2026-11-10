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


def test_week_config_from_template_jour_absent_vaut_zero():
    """Un jour absent du modèle (case laissée vide) vaut 0, jamais 8 h
    (retour du 10/11, modèle « femme de ménage » 6 h/semaine)."""
    cfg = week_config_from_template(
        [
            {"day": 3, "hours": 3, "type": "travail"},
            {"day": 6, "hours": 3, "type": "travail"},
        ]
    )
    assert cfg["monday"] == {"type": "weekend", "hours": 0.0}
    assert cfg["wednesday"] == {"type": "travail", "hours": 3.0}
    assert cfg["saturday"] == {"type": "travail", "hours": 3.0}
    assert sum(j["hours"] for j in cfg.values()) == 6.0
