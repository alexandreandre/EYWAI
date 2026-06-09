"""Tests déductions OETH."""

from __future__ import annotations

from app.modules.oeth_settings.application import calculator
from app.modules.oeth_settings.domain.constants import DEFAULT_OETH_CONFIG


def test_deduction_ecap_reduces_contribution():
    result = calculator.compute_annual_contribution(
        employment_year=2025,
        ema_assujettissement=100.0,
        ema_boeth_interne=0.0,
        ema_boeth_externe=0.0,
        ema_ecap=2.0,
        smic_horaire=11.88,
        taux_obligation=0.06,
        deductions={"062": 500.0},
        config=DEFAULT_OETH_CONFIG,
    )
    assert result["contribution_brute"] > result["contribution_nette"]
    assert result["deductions_detail"]["060"] > 0
    assert result["deductions_detail"]["062"] == 500.0
