"""Réduction générale d'un mois d'activité partielle (R-338, premier cas : LEWIS).

Règle de l'oracle R-H11 (`scripts/verification_rgdu`) : l'indemnité d'activité
partielle reste hors du brut et les heures chômées sortent du SMIC de référence.
Martine retire les heures chômées saisies des heures rémunérées : 35 h sur
151,67 h, salaire de 2 000 €.
"""

from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.documents import payslip_run_heures
from app.modules.payroll.engine.calcul_reduction_generale import (
    _calculer_smic_de_reference_cumule,
    _smic_horaire_de_reference,
    calculer_reduction_generale,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

BRUT_PLEIN = 2000.0
HEURES_PLEINES = 151.67
HEURES_CHOMEES = 35.0
BRUT_REDUIT = round(BRUT_PLEIN - HEURES_CHOMEES * BRUT_PLEIN / HEURES_PLEINES, 2)
HEURES_REMUNEREES = round(HEURES_PLEINES - HEURES_CHOMEES, 2)


def _reduction(brut: float, heures: float) -> float:
    contexte = build_test_contexte(salaire_base=BRUT_PLEIN)
    ligne = calculer_reduction_generale(contexte, brut, heures)
    return abs(float(ligne["montant_patronal"]))


def test_le_smic_de_reference_perd_les_heures_chomees():
    contexte = build_test_contexte(salaire_base=BRUT_PLEIN)
    smic = _calculer_smic_de_reference_cumule(contexte, HEURES_REMUNEREES)
    # Le SMIC horaire du barème de test, pour les seules heures rémunérées.
    assert smic == round(_smic_horaire_de_reference(contexte) * HEURES_REMUNEREES, 2)
    assert smic < round(_smic_horaire_de_reference(contexte) * HEURES_PLEINES, 2)


def test_meme_taux_horaire_meme_coefficient_que_le_mois_plein():
    plein = _reduction(BRUT_PLEIN, HEURES_PLEINES)
    reduit = _reduction(BRUT_REDUIT, HEURES_REMUNEREES)
    assert reduit == pytest.approx(plein * BRUT_REDUIT / BRUT_PLEIN, abs=0.5)


def test_sans_retirer_les_heures_chomees_la_reduction_serait_trop_forte():
    assert _reduction(BRUT_REDUIT, HEURES_REMUNEREES) < _reduction(BRUT_REDUIT, HEURES_PLEINES)


def test_le_pipeline_retire_les_heures_chomees_et_garde_l_indemnite_hors_du_brut():
    source = inspect.getsource(payslip_run_heures.run_payslip_generation_heures)
    assert "max(0.0, heures_base_mois - heures_activite_partielle)" in source
    assert 'heures_chomees_saisie = abs(float(saisie.get("quantity") or 0.0))' in source
    # L'indemnité part au canal des revenus de remplacement, hors primes soumises.
    assert '"prime_id": "indemnite_activite_partielle"' in source
