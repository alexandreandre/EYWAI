"""Tests unitaires — analytics paie (agrégations pures)."""

from app.modules.payroll.application.analytics_queries import (
    _extract_amounts,
    _pct_delta,
    _parse_period,
    _period_key,
    _shift_month,
)


def test_parse_period():
    y, m = _parse_period("2026-05")
    assert y == 2026
    assert m == 5


def test_period_key():
    assert _period_key(2026, 5) == "2026-05"


def test_shift_month():
    assert _shift_month(2026, 1, -1) == (2025, 12)
    assert _shift_month(2025, 12, 1) == (2026, 1)


def test_extract_amounts():
    data = {
        "salaire_brut": 3000,
        "net_a_payer": 2200,
        "pied_de_page": {"cout_total_employeur": 4000},
        "structure_cotisations": {
            "cotisations": [
                {"montant_salarial": 100, "montant_patronal": 200},
            ]
        },
    }
    out = _extract_amounts(data)
    assert out["brut"] == 3000
    assert out["net"] == 2200
    assert out["cout_employeur"] == 4000
    assert out["cotisations_salariales"] == 100
    assert out["cotisations_patronales"] == 200


def test_pct_delta():
    assert _pct_delta(110, 100) == 10.0
    assert _pct_delta(0, 0) is None
    assert _pct_delta(50, 0) == 100.0
