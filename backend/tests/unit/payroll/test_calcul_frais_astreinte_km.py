"""Tests unitaires — indemnité km astreinte (cas Excel Elsa)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_frais import (
    coefficient_a_km,
    indemnite_km_astreinte,
)
from tests.unit.payroll.fixtures.baremes_km_excel import baremes_km_excel_fixture


@pytest.fixture
def baremes_km():
    return baremes_km_excel_fixture()


def test_coefficient_a_7cv(baremes_km):
    assert coefficient_a_km(baremes_km, "voitures", 7) == pytest.approx(0.697, abs=0.001)


def test_coefficient_a_4cv(baremes_km):
    assert coefficient_a_km(baremes_km, "voitures", 4) == pytest.approx(0.606, abs=0.001)


def test_joubert_excel(baremes_km):
    amount, details = indemnite_km_astreinte(
        baremes_km,
        22.2,
        7,
        "voitures",
        threshold_one_way=10,
        round_trip_multiplier=2,
        rate_mode="coefficient_a",
    )
    assert details["km_eligible"] == pytest.approx(24.4, abs=0.01)
    assert amount == pytest.approx(17.01, abs=0.01)


def test_dupont_below_threshold(baremes_km):
    amount, details = indemnite_km_astreinte(
        baremes_km,
        1.0,
        7,
        "voitures",
    )
    assert amount is None
    assert details["skip_reason"] == "below_threshold"


def test_hauchecorne_excel(baremes_km):
    amount, _ = indemnite_km_astreinte(
        baremes_km,
        35.0,
        4,
        "voitures",
    )
    assert amount == pytest.approx(30.30, abs=0.01)


def test_kocis_excel(baremes_km):
    amount, _ = indemnite_km_astreinte(
        baremes_km,
        15.4,
        4,
        "voitures",
    )
    assert amount == pytest.approx(6.55, abs=0.01)
