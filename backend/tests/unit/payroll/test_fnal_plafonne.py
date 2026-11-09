"""FNAL : 0,10 % sur le salaire limité au plafond sous 50 salariés (CTP 332),
0,50 % sur la totalité à partir de 50 (CTP 236). Décision d'Alexandre du 09/11/2026."""

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _fnal(effectif, brut):
    ctx = build_test_contexte(effectif=effectif)
    lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)
    return next(l for l in lignes if (l.get("id") or l.get("coti_id")) == "fnal")


def test_sous_50_salaries_la_base_s_arrete_au_plafond():
    ligne = _fnal(10, 6000.0)
    assert ligne["base"] < 6000.0
    assert ligne["montant_patronal"] == pytest.approx(ligne["base"] * 0.001, abs=0.01)


def test_a_50_salaries_la_base_est_le_salaire_entier():
    ligne = _fnal(70, 6000.0)
    assert ligne["base"] == pytest.approx(6000.0)
    assert ligne["montant_patronal"] == pytest.approx(30.0, abs=0.01)


def test_sous_le_plafond_la_base_ne_change_pas():
    assert _fnal(10, 2500.0)["base"] == pytest.approx(2500.0)
