"""Franchise de cotisations de la gratification de stage.

Urssaf, « Accueillir un stagiaire étudiant » (2026) : plafond horaire de la
Sécurité sociale 30 €, gratification minimale et limite d'exonération 4,50 €
par heure de stage (15 %).
https://www.urssaf.fr/accueil/employeur/embaucher-gerer-salaries/embaucher/stagiaire-etudiant.html

Le plafond horaire est fixé par arrêté : il vient des barèmes, jamais du
plafond mensuel divisé par 151,67 h (4 005 / 151,67 × 15 % = 3,96 €/h).
"""

from __future__ import annotations

import copy

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.exoneration_stage import plafond_exoneration_stage

from .fixtures.baremes_snapshot import baremes_snapshot
from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

HEURES_MOIS = 35 * 52 / 12  # heures du mois de référence d'un stage à 35 h
CODE_ALERTE_PLAFOND_HORAIRE_ABSENT = "stage_plafond_horaire_ss_absent"


def _baremes_2026(plafond_horaire_ss: float | None = 30.0) -> dict:
    baremes = copy.deepcopy(baremes_snapshot())
    if plafond_horaire_ss is not None:
        baremes["stage"]["plafond_horaire_ss"] = plafond_horaire_ss
    return baremes


def _stagiaire(gratification: float, baremes: dict | None = None):
    return build_test_contexte(
        salaire_base=gratification,
        type_contrat="Stage",
        baremes=baremes if baremes is not None else _baremes_2026(),
    )


def test_franchise_2026_de_4_50_euros_par_heure():
    ctx = _stagiaire(600.0)
    assert plafond_exoneration_stage(ctx, 1.0) == 4.50
    assert plafond_exoneration_stage(ctx, 100.0) == 450.00
    assert plafond_exoneration_stage(ctx, HEURES_MOIS) == 682.50


def test_gratification_de_4_40_euros_par_heure_exoneree():
    brut = round(4.40 * HEURES_MOIS, 2)
    lignes, total = calculer_cotisations(_stagiaire(brut), brut)
    assert total == 0.0
    assert [l["coti_id"] for l in lignes] == ["exoneration_stage"]
    assert lignes[0]["base"] == brut


def test_gratification_de_4_60_euros_par_heure_cotisee_sur_0_10_euro_par_heure():
    brut = round(4.60 * HEURES_MOIS, 2)
    lignes, total = calculer_cotisations(_stagiaire(brut), brut)
    exoneree = next(l for l in lignes if l["coti_id"] == "exoneration_stage")
    assert exoneree["base"] == 682.50
    residuel = round(0.10 * HEURES_MOIS, 2)
    maladie = next(l for l in lignes if l.get("coti_id") == "securite_sociale_maladie")
    assert maladie["base"] == pytest.approx(residuel, abs=0.01)
    assert total > 0


def test_sans_plafond_horaire_officiel_pas_de_franchise_devinee_et_une_alerte():
    ctx = _stagiaire(600.0, _baremes_2026(plafond_horaire_ss=None))
    lignes, total = calculer_cotisations(ctx, 600.0)
    assert not any(l.get("coti_id") == "exoneration_stage" for l in lignes)
    assert total > 0
    alertes = [a for a in ctx.alertes_baremes if a.get("code") == CODE_ALERTE_PLAFOND_HORAIRE_ABSENT]
    assert len(alertes) == 1
    assert alertes[0]["critique"] is True
    assert "plafond horaire" in alertes[0]["message"]
    # Un second calcul du même bulletin ne double pas l'alerte.
    calculer_cotisations(ctx, 600.0)
    assert len([a for a in ctx.alertes_baremes if a.get("code") == CODE_ALERTE_PLAFOND_HORAIRE_ABSENT]) == 1
