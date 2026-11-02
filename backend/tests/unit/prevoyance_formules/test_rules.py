"""Règles des formules de prévoyance de la société (conception du 02/11/2026)."""

from __future__ import annotations

import copy

import pytest

from app.modules.prevoyance_formules.domain.rules import (
    appliquer_formule,
    fiche_a_mettre_a_jour,
    formule_convient,
    lignes_identiques,
)

pytestmark = pytest.mark.unit

LIGNE_TA = {"libelle": "Prévoyance TA", "salarial": 0.005, "patronal": 0.007, "forfait_social": 0.08}
LIGNE_TB = {
    "libelle": "Prévoyance TB",
    "salarial": 0.01,
    "patronal": 0.012,
    "forfait_social": 0.08,
    "base": "tranche_2",
}
FORMULE = {"id": "f1", "libelle": "Cadres", "statut_categoriel": "cadre", "lignes": [LIGNE_TA, LIGNE_TB]}


def test_appliquer_copie_les_lignes_et_pose_la_formule():
    resultat = appliquer_formule({"adhesion": True, "lignes_specifiques": [{"libelle": "Ancienne"}]}, FORMULE)
    assert resultat["formule_id"] == "f1"
    assert [l["libelle"] for l in resultat["lignes_specifiques"]] == ["Prévoyance TA", "Prévoyance TB"]
    assert resultat["lignes_specifiques"][1]["base"] == "tranche_2"


def test_appliquer_numerote_les_lignes():
    resultat = appliquer_formule({"adhesion": True}, FORMULE)
    assert [l["id"] for l in resultat["lignes_specifiques"]] == ["prevoyance_1", "prevoyance_2"]


def test_appliquer_garde_l_adhesion_et_les_autres_cles():
    resultat = appliquer_formule({"adhesion": False, "organisme": "X"}, FORMULE)
    assert resultat["adhesion"] is False
    assert resultat["organisme"] == "X"


def test_appliquer_sans_prevoyance_ouvre_l_adhesion():
    assert appliquer_formule(None, FORMULE)["adhesion"] is True


def test_appliquer_ne_modifie_ni_la_fiche_ni_la_formule():
    prevoyance = {"adhesion": True, "lignes_specifiques": []}
    avant_fiche, avant_formule = copy.deepcopy(prevoyance), copy.deepcopy(FORMULE)
    resultat = appliquer_formule(prevoyance, FORMULE)
    resultat["lignes_specifiques"][0]["salarial"] = 1
    assert prevoyance == avant_fiche
    assert FORMULE == avant_formule


def test_lignes_identiques_sans_tenir_compte_des_identifiants_ni_de_la_base_par_defaut():
    fiche = [
        {**LIGNE_TA, "id": "prevoyance_7", "base": "brut_plafonne", "salarial": "0.005"},
        {**LIGNE_TB, "id": "x"},
    ]
    assert lignes_identiques(fiche, [LIGNE_TA, LIGNE_TB])


def test_une_ligne_en_plus_ou_un_taux_change_rend_les_lignes_differentes():
    assert not lignes_identiques([LIGNE_TA], [LIGNE_TA, LIGNE_TB])
    assert not lignes_identiques([{**LIGNE_TA, "patronal": 0.008}], [LIGNE_TA])
    assert not lignes_identiques([{**LIGNE_TB, "base": "brut"}], [LIGNE_TB])


def test_fiche_a_mettre_a_jour_seulement_si_elle_porte_la_formule_et_diverge():
    a_jour = {"prevoyance": {"adhesion": True, "formule_id": "f1", "lignes_specifiques": [LIGNE_TA, LIGNE_TB]}}
    ancienne = {"prevoyance": {"adhesion": True, "formule_id": "f1", "lignes_specifiques": [LIGNE_TA]}}
    autre = {"prevoyance": {"adhesion": True, "formule_id": "f2", "lignes_specifiques": [LIGNE_TA]}}
    assert not fiche_a_mettre_a_jour(a_jour, FORMULE)
    assert fiche_a_mettre_a_jour(ancienne, FORMULE)
    assert not fiche_a_mettre_a_jour(autre, FORMULE)
    assert not fiche_a_mettre_a_jour({}, FORMULE)


@pytest.mark.parametrize(
    "categorie, cadre, attendu",
    [("tous", True, True), ("tous", False, True), ("cadre", True, True), ("cadre", False, False),
     ("non_cadre", False, True), ("non_cadre", True, False)],
)
def test_formule_convient_selon_la_categorie(categorie, cadre, attendu):
    assert formule_convient({"statut_categoriel": categorie}, cadre) is attendu
