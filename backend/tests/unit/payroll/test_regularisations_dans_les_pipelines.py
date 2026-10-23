"""Les deux générateurs et les deux pipelines traitent la régularisation au même endroit."""

from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_forfait,
    payslip_run_heures,
)
from app.modules.payroll.engine import (
    calcul_brut,
    calcul_brut_forfait,
    calcul_cotisations,
    calcul_net,
    calcul_reduction_generale,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("module", [payslip_generator, payslip_generator_forfait])
def test_chaque_generateur_range_les_corrections_avant_les_primes(module):
    source = inspect.getsource(module)
    assert "ranger_correction_manuelle(row, saisies_data)" in source
    assert "ranger_regularisation(row, saisies_data)" not in source
    assert source.index("ranger_correction_manuelle(row, saisies_data)") < source.index("est_saisie_ijss_validees(row)")


@pytest.mark.parametrize("module", [payslip_run_heures, payslip_run_forfait])
def test_chaque_pipeline_pose_les_regularisations_entre_la_reduction_et_le_net(module):
    source = inspect.getsource(module)
    pose = source.index("ajouter_regularisations(")
    assert source.index("calculer_reduction_generale(") < pose < source.index("resultats_nets = calculer_net_et_impot(")
    assert "regularisation_reduction_generale=effet_regul.reduction_generale" in source


@pytest.mark.parametrize(
    "module, calcul_du_brut",
    [(payslip_run_heures, "calculer_salaire_brut("), (payslip_run_forfait, "calculer_salaire_brut_forfait(")],
)
def test_chaque_pipeline_pose_les_corrections_aux_memes_etapes(module, calcul_du_brut):
    """Spec § 5 : le module des corrections est appelé aux mêmes étapes des deux copies."""
    source = inspect.getsource(module)
    journal = source.index("contexte.corrections_du_mois = JournalDesCorrections.depuis(saisie_du_mois)")
    brut = source.index(f"resultat_brut = {calcul_du_brut}")
    maintien = source.index("lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(")
    gains = source.index("effet_gains = corriger_les_lignes_de_gain(details_brut, contexte.corrections_du_mois)")
    cotisations = source.index("lignes_cotisations, total_salarial = calculer_cotisations(")
    reduction = source.index("calculer_reduction_generale(")
    passe_cotisations = source.index(
        "effet_cotisations = corriger_les_lignes_de_cotisation(lignes_cotisations, contexte.corrections_du_mois)"
    )
    regul = source.index("ajouter_regularisations(")
    net = source.index("resultats_nets = calculer_net_et_impot(")
    assemblage = source.rindex("bulletin_final = creer_bulletin_final(")
    attente = source.index("poser_les_corrections_en_attente(bulletin_final, contexte.corrections_du_mois)")
    cumuls = source.index("mettre_a_jour_cumuls(")
    assert journal < brut < maintien < gains < cotisations
    assert reduction < passe_cotisations < regul < net
    assert assemblage < attente < cumuls
    assert "synchroniser_le_maintien(resultats_maintien, details_brut)" in source


@pytest.mark.parametrize(
    "module, fonction",
    [
        (calcul_brut, "calculer_salaire_brut"),
        (calcul_brut_forfait, "calculer_salaire_brut_forfait"),
        (calcul_cotisations, "calculer_cotisations"),
    ],
)
def test_chaque_producteur_de_lignes_les_pose_dans_des_lignes_corrigees(module, fonction):
    """Une ligne ne peut pas naître sans passer par sa correction."""
    source = inspect.getsource(getattr(module, fonction))
    assert "LignesCorrigees(journal_du_contexte(contexte)" in source
    assert "lignes_composants_brut = []" not in source and "bulletin_cotisations = []" not in source


def test_la_reduction_et_l_impot_lisent_leur_correction():
    assert "corriger_la_reduction_generale(" in inspect.getsource(calcul_reduction_generale.calculer_reduction_generale)
    assert "corriger_le_taux_d_impot(" in inspect.getsource(calcul_net.calculer_net_et_impot)
