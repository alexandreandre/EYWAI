"""Tests recette barème astreinte complet."""

from datetime import date

from app.modules.payroll_variables.domain.astreinte_week import compute_week_payouts
from app.modules.payroll_variables.domain.astreinte_weekend_majoration import (
    evaluate_astreinte_weekend_majoration,
)
from app.modules.payroll_variables.domain.hourly_rate import resolve_hourly_rate
from tests.unit.payroll_variables.recette_astreinte_complete import (
    RECETTE_AMOUNTS,
    RECETTE_EXPORT_CODES,
    RECETTE_RULE_CODES,
)


def test_recette_amounts_configured():
    assert RECETTE_AMOUNTS["amount_normal"] == 176.18
    assert RECETTE_AMOUNTS["amount_christmas"] == 352.36
    assert RECETTE_AMOUNTS["amount_bridge"] == 250.0


def test_recette_export_codes():
    assert "BPAS" in RECETTE_EXPORT_CODES
    assert RECETTE_RULE_CODES == (
        "astreinte_week",
        "astreinte_sat",
        "astreinte_sun",
        "astreinte_km",
    )


def test_recette_scenario_march_astreinte_with_saturday():
    """Semaine normale + intervention samedi (1 h forfait 25 %)."""
    conditions = {**RECETTE_AMOUNTS, "christmas_mode": "replace", "bridge_mode": "add"}
    monday = date(2026, 3, 2)
    week_lines = compute_week_payouts(
        monday,
        [date(2026, 3, 5)],
        [],
        [],
        conditions,
        year=2026,
    )
    assert week_lines[0]["amount"] == 176.18

    hourly = resolve_hourly_rate(
        {"salaire_de_base": {"valeur": 2600}, "duree_hebdomadaire": 35}
    )
    assert hourly > 0

    maj_rule = {
        "code": "astreinte_sat",
        "conditions": {"weekday_rates": {"5": 0.25}, "weekend_weekday_numbers": [5]},
    }
    maj = evaluate_astreinte_weekend_majoration(
        maj_rule,
        year=2026,
        month=3,
        calendrier_reel=[{"jour": 7, "heures_faites": 2.0}],
        astreinte_shift_dates=[date(2026, 3, 7)],
        hourly_rate=hourly,
    )
    assert len(maj) == 1
    assert maj[0]["amount"] == round(hourly * 0.25, 2)
