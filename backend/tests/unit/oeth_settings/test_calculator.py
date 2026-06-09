"""Tests unitaires moteur calcul OETH."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.oeth_settings.application import calculator
from app.modules.oeth_settings.domain import rules
from app.modules.oeth_settings.domain.constants import DEFAULT_OETH_CONFIG


def test_quota_boeth_floor():
    assert rules.quota_boeth(25.0, 0.06) == 1
    assert rules.quota_boeth(100.0, 0.06) == 6


def test_coefficient_taille():
    assert rules.coefficient_taille(50, DEFAULT_OETH_CONFIG) == 400
    assert rules.coefficient_taille(300, DEFAULT_OETH_CONFIG) == 500
    assert rules.coefficient_taille(800, DEFAULT_OETH_CONFIG) == 600


def test_boeth_50_plus_factor():
    birth = date(1970, 6, 1)
    assert rules.boeth_50_plus_factor(birth, 2025, DEFAULT_OETH_CONFIG) == 1.5
    assert rules.boeth_50_plus_factor(date(1990, 1, 1), 2025, DEFAULT_OETH_CONFIG) == 1.0


def test_neutralisation_active():
    franchissement = date(2022, 1, 1)
    assert rules.is_neutralisation_active(franchissement, 2024, DEFAULT_OETH_CONFIG) is True
    assert rules.is_neutralisation_active(franchissement, 2028, DEFAULT_OETH_CONFIG) is False


def test_monthly_etp_full_month():
    etp = calculator.monthly_etp(date(2020, 1, 1), None, 2025, 6)
    assert etp == pytest.approx(1.0)


def test_monthly_etp_mid_month_hire():
    etp = calculator.monthly_etp(date(2025, 6, 15), None, 2025, 6)
    assert 0 < etp < 1.0


def test_compute_annual_contribution_basic():
    result = calculator.compute_annual_contribution(
        employment_year=2025,
        ema_assujettissement=100.0,
        ema_boeth_interne=3.0,
        ema_boeth_externe=0.0,
        ema_ecap=0.0,
        smic_horaire=11.88,
        taux_obligation=0.06,
        deductions={},
        config=DEFAULT_OETH_CONFIG,
    )
    assert result["quota_boeth"] == 6
    assert result["boeth_manquants"] == 3
    assert result["contribution_brute"] == pytest.approx(3 * 400 * 11.88)


def test_compute_annual_contribution_neutralisation():
    result = calculator.compute_annual_contribution(
        employment_year=2025,
        ema_assujettissement=100.0,
        ema_boeth_interne=0.0,
        ema_boeth_externe=0.0,
        ema_ecap=0.0,
        smic_horaire=11.88,
        taux_obligation=0.06,
        deductions={},
        config=DEFAULT_OETH_CONFIG,
        neutralisation_active=True,
    )
    assert result["contribution_due"] == 0.0


def test_compute_ema_from_employees():
    employees = [
        {
            "hire_date": "2020-01-01",
            "end_date": None,
            "date_naissance": "1980-01-01",
            "boeth": {
                "boeth_code": "01",
                "valid_from": "2020-01-01",
                "valid_to": None,
            },
        },
        {
            "hire_date": "2021-01-01",
            "end_date": None,
            "date_naissance": "1995-01-01",
            "boeth": {},
        },
    ]
    ema = calculator.compute_ema_from_employees(employees, 2025)
    assert ema["ema_assujettissement"] == pytest.approx(2.0, rel=0.01)
    assert ema["ema_boeth_interne"] == pytest.approx(1.0, rel=0.01)
