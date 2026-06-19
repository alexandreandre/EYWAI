"""Tests unitaires — rémunération de référence ICCP."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.modules.payroll.engine.reference_remuneration import (
    ajouter_prime_precarite_si_cdd,
    calculer_iccp_l1243_8,
    estimer_extras_fin_contrat,
    get_cp_reference_period_bounds,
    lire_brut_total_contrat,
    lire_bruts_depuis_cumuls,
    lire_bruts_periode_reference,
    mettre_a_jour_brut_reference_cumul,
)


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def match(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return type("R", (), {"data": self._data})()


class _FakeSupabase:
    def __init__(self, payslip_brut: float | None):
        self._payslip_brut = payslip_brut

    def table(self, name):
        assert name == "payslips"
        if self._payslip_brut is None:
            return _FakeQuery(None)
        return _FakeQuery({"payslip_data": {"salaire_brut": self._payslip_brut}})


def test_periode_reference_juin():
    start, end = get_cp_reference_period_bounds(date(2025, 9, 15))
    assert start == date(2025, 6, 1)
    assert end == date(2026, 5, 31)


def test_lire_bruts_avec_bulletin():
    sb = _FakeSupabase(2200.0)
    ref = lire_bruts_periode_reference(
        "emp-1",
        date(2025, 9, 15),
        sb,
        salaire_contractuel_fallback=0.0,
    )
    assert ref.base_totale > 0
    assert ref.mois_avec_bulletin >= 1


def test_lire_bruts_fallback_contractuel():
    sb = _FakeSupabase(None)
    ref = lire_bruts_periode_reference(
        "emp-1",
        date(2025, 9, 15),
        sb,
        salaire_contractuel_fallback=2000.0,
    )
    assert ref.base_totale > 0
    assert ref.alertes


def test_ajouter_precarite_cdd():
    base, extra = ajouter_prime_precarite_si_cdd(
        10000.0, is_cdd=True, montant_precarite=1000.0
    )
    assert base == 11000.0
    assert extra == 1000.0


def test_iccp_l1243_8():
    assert calculer_iccp_l1243_8(10000.0, montant_precarite=1000.0) == pytest.approx(
        1100.0, abs=0.01
    )


def test_mise_a_jour_brut_reference_cumul(tmp_path: Path):
    data = {"cumuls": {}}
    ref_date = date(2025, 9, 15)
    mettre_a_jour_brut_reference_cumul(data, 2200.0, ref_date)
    assert data["cumuls"]["brut_reference_n_1"] == 2200.0
    mettre_a_jour_brut_reference_cumul(data, 2300.0, ref_date)
    assert data["cumuls"]["brut_reference_n_1"] == 4500.0


def test_lire_bruts_depuis_cumuls(tmp_path: Path):
    cumuls_dir = tmp_path / "cumuls"
    cumuls_dir.mkdir()
    (cumuls_dir / "01.json").write_text(
        json.dumps({"cumuls": {"brut_total": 2200.0}}), encoding="utf-8"
    )
    (cumuls_dir / "02.json").write_text(
        json.dumps({"cumuls": {"brut_total": 4400.0}}), encoding="utf-8"
    )
    ref = lire_bruts_depuis_cumuls(
        tmp_path, date(2025, 1, 1), date(2025, 2, 28)
    )
    assert ref.base_totale == pytest.approx(2200.0, abs=0.01)


def test_lire_brut_total_contrat():
    sb = _FakeSupabase(2200.0)
    total, alertes = lire_brut_total_contrat(
        "emp-1",
        date(2025, 1, 1),
        date(2025, 3, 31),
        sb,
        salaire_contractuel_fallback=2000.0,
    )
    assert total > 0


def test_estimer_extras_fin_contrat_cdd():
    baremes = {"cdd": {"precarite": {"taux": 0.10}}}
    prec, ifm = estimer_extras_fin_contrat(
        10000.0, baremes, is_cdd=True, is_interim=False
    )
    assert prec == pytest.approx(1000.0, abs=0.01)
    assert ifm == 0.0
