"""Prévoyance cadre tranche B : la régularisation du plafond s'applique aussi.

Comitech, septembre 2026 : un cadre dont le brut repasse sous le plafond voit
sa tranche 2 cumulée régularisée (assiette négative). EYWAI régularisait la
retraite complémentaire mais sautait la ligne de prévoyance tranche B de la
fiche ; l'ancien logiciel rend 2,91 € au salarié (−255 × 1,14 %).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

LIGNES = [
    {"id": "prev_ta", "base": "brut_plafonne", "libelle": "Prévoyance cadre TA",
     "salarial": 0.00365, "patronal": 0.01825, "forfait_social": 0.08},
    {"id": "prev_tb", "base": "tranche_2", "libelle": "Prévoyance cadre TB",
     "salarial": 0.0114, "patronal": 0.01709, "forfait_social": 0.08},
]


def test_la_tranche_b_negative_rend_la_cotisation():
    pss = build_test_contexte().baremes["pss"]["mensuel"]
    deja = 255.0
    ctx = build_test_contexte(
        statut="Cadre",
        salaire_base=3750.0,
        cumuls={
            "cumul_brut_agirc_arrco": 8 * pss + deja,
            "cumul_pss_agirc_arrco": 8 * pss,
            "cumul_tranche_1_appliquee": 8 * pss,
            "cumul_tranche_2_appliquee": deja,
        },
        specificites_extra={"prevoyance": {"adhesion": True, "lignes_specifiques": LIGNES}},
    )
    ctx.month = 9
    lignes, _ = calculer_cotisations(ctx, 3750.0, 0.0, 0.0)
    assiette = max(0.0, deja + 3750.0 - pss) - deja
    assert assiette < 0
    tb = next((l for l in lignes if l.get("libelle") == "Prévoyance cadre TB"), None)
    assert tb is not None
    assert tb["montant_salarial"] == pytest.approx(round(assiette * 0.0114, 2), abs=0.01)
    assert tb["montant_patronal"] == pytest.approx(round(assiette * 0.01709, 2), abs=0.01)


def test_sans_regularisation_rien_ne_change():
    ctx = build_test_contexte(
        statut="Cadre",
        salaire_base=3000.0,
        specificites_extra={"prevoyance": {"adhesion": True, "lignes_specifiques": LIGNES}},
    )
    ctx.month = 1
    lignes, _ = calculer_cotisations(ctx, 3000.0, 0.0, 0.0)
    assert not any(l.get("libelle") == "Prévoyance cadre TB" for l in lignes)
