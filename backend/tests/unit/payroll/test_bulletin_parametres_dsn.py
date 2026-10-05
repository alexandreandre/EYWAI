"""Paramètres du bulletin dont la DSN a besoin.

Le bulletin garde le plafond de la période, proratisé (`pss_mensuel`). La DSN
en tire les jours du plafond (S21.G00.53 unité 40) : il lui faut aussi le
plafond plein du barème, que le bulletin ne gardait pas.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from tests.unit.payroll.helpers import build_test_contexte


def _parametres(ratio=None):
    ctx = build_test_contexte(salaire_base=2000.0)
    ctx.year = 2026
    if ratio is not None:
        ctx.ratio_plafond_ss = ratio
    lignes, total_sal = calculer_cotisations(ctx, 2000.0)
    nets = calculer_net_et_impot(ctx, 2000.0, lignes, total_sal, [], 0.0)
    return creer_bulletin_final(ctx, 2000.0, [], lignes, nets, [], 2026, 6)["parametres"]


def test_le_bulletin_garde_le_plafond_plein_a_cote_du_plafond_de_la_periode():
    parametres = _parametres(ratio=29 / 30)
    plein = parametres["pss_mensuel_plein"]
    assert plein > 0
    assert parametres["pss_mensuel"] == pytest.approx(round(plein * 29 / 30, 2))


def test_sans_proratisation_les_deux_plafonds_sont_egaux():
    parametres = _parametres()
    assert parametres["pss_mensuel_plein"] == parametres["pss_mensuel"]
