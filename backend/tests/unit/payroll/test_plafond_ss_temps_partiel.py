"""Plafond de la Sécurité sociale d'un salarié à temps partiel.

Code de la sécurité sociale, art. R242-7 : pour un salarié à temps partiel, le
plafond est réduit selon le rapport entre la durée de travail prévue au contrat
et la durée légale (ou conventionnelle si elle est inférieure). La règle vaut
pour toute fiche à temps partiel ; la clé `proratiser_plafond_ss` ne sert plus
qu'à la couper explicitement.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

PSS_2026 = 4005.0


def _assiettes(brut: float, **contrat) -> dict:
    ctx = build_test_contexte(salaire_base=brut, type_contrat="CDI", **contrat)
    return _calculer_assiettes(ctx, brut, 0.0)


def test_temps_partiel_a_24_h_plafond_proratise():
    a = _assiettes(1500.0, duree_hebdo=24.0, is_temps_partiel=True)
    assert a["plafond_ss"] == 2746.29  # 4 005 × 24 / 35


def test_au_dessus_de_sa_fraction_la_tranche_1_est_bornee():
    a = _assiettes(3500.0, duree_hebdo=24.0, is_temps_partiel=True)
    assert a["brut_plafonne"] == 2746.29
    assert a["tranche_2"] == pytest.approx(3500.0 - 2746.29, abs=0.01)


def test_temps_plein_inchange():
    a = _assiettes(4500.0, duree_hebdo=35.0, is_temps_partiel=False)
    assert a["plafond_ss"] == PSS_2026
    assert a["brut_plafonne"] == PSS_2026
    assert a["tranche_2"] == pytest.approx(495.0, abs=0.01)


def test_la_cle_explicite_a_faux_coupe_la_proratisation():
    a = _assiettes(3500.0, duree_hebdo=24.0, is_temps_partiel=True, proratiser_plafond_ss=False)
    assert a["plafond_ss"] == PSS_2026
    assert a["brut_plafonne"] == 3500.0
