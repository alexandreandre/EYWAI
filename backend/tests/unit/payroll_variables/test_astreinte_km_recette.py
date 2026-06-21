"""Tests recette — configuration indemnité km astreinte (cas Excel Elsa)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_frais import indemnite_km_astreinte
from tests.unit.payroll.fixtures.baremes_km_excel import baremes_km_excel_fixture
from tests.unit.payroll_variables.recette_astreinte_km import (
    RECETTE_EMPLOYEES,
    RECETTE_RULE,
)


def test_recette_rule_structure():
    assert RECETTE_RULE["rule_type"] == "per_astreinte_weekend_km"
    assert RECETTE_RULE["conditions"]["km_free_threshold_one_way"] == 10


@pytest.mark.parametrize(
    "row",
    [e for e in RECETTE_EMPLOYEES if "expected_eur" in e],
)
def test_recette_employee_amounts(row):
    baremes = baremes_km_excel_fixture()
    amount, details = indemnite_km_astreinte(
        baremes,
        row["distance_km_one_way"],
        row["vehicle_cv"],
        "voitures",
        threshold_one_way=RECETTE_RULE["conditions"]["km_free_threshold_one_way"],
        round_trip_multiplier=RECETTE_RULE["conditions"]["round_trip_multiplier"],
        rate_mode=RECETTE_RULE["conditions"]["rate_mode"],
    )
    assert amount == pytest.approx(row["expected_eur"], abs=0.02), row["name"]


def test_recette_dupont_skip():
    baremes = baremes_km_excel_fixture()
    dupont = next(e for e in RECETTE_EMPLOYEES if e["name"] == "DUPONT")
    amount, details = indemnite_km_astreinte(
        baremes,
        dupont["distance_km_one_way"],
        dupont["vehicle_cv"],
        "voitures",
    )
    assert amount is None
    assert details["skip_reason"] == dupont["expected_skip"]
