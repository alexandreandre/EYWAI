"""Indemnité compensatrice de congés payés (ICCP) au dernier mois d'un CDD."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from .helpers import build_test_contexte


def _lignes_gain(res):
    return {l["libelle"]: l["gain"] for l in res["lignes_composants_brut"] if l.get("gain")}


def test_iccp_cdd_dernier_mois():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert "Prime de précarité (CDD)" in gains
    iccp = next(
        (v for k, v in gains.items() if "compensatrice de congés" in k), None
    )
    assert iccp is not None
    # Précarité = 10 % de (8800 + 2200) = 1100 ; ICCP = 10 % de (8800+2200+1100).
    assert gains["Prime de précarité (CDD)"] == pytest.approx(1100.0, abs=0.05)
    assert iccp == pytest.approx(1210.0, abs=0.05)


def test_iccp_absente_si_pas_dernier_mois():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-08-31",
        cumuls={"brut_total": 8800.0},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert not any("compensatrice de congés" in k for k in gains)
    assert "Prime de précarité (CDD)" not in gains


def test_iccp_desactivable_par_flag():
    ctx = build_test_contexte(
        salaire_base=2200.0,
        type_contrat="CDD",
        date_entree="2025-10-01",
        date_fin_contrat="2026-04-30",
        cumuls={"brut_total": 8800.0},
        specificites_extra={"cdd_sans_iccp": True},
    )
    res = calculer_salaire_brut(ctx, [], date(2026, 4, 1), date(2026, 4, 30), [])
    gains = _lignes_gain(res)
    assert not any("compensatrice de congés" in k for k in gains)
    # La précarité reste due.
    assert "Prime de précarité (CDD)" in gains
