"""Indemnité de licenciement et de rupture conventionnelle de la métallurgie.

CCN de la métallurgie (IDCC 3248), art. 75.3.1.1, 75.3.1.2, 75.3.3 et 76.2
(Légifrance, ouverts le 04/11/2026). Audit du 03/11/2026 (lot F, verdict 1) :
une rupture conventionnelle d'un cadre du groupe F, 15 ans et 5 mois
d'ancienneté, 4 250 € de salaire de référence, payée au minimum légal ;
dû : 4 250 × (7/5 + 8,4167 × 3/5) = 27 412,50 €.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnite_rupture_conventionnelle,
    calculer_indemnites_sortie,
)
from app.modules.payroll.engine.indemnite_licenciement_metallurgie import (
    groupe_d_emplois,
    indemnite_licenciement_metallurgie,
)
from tests.unit.payroll.test_indemnite_legale_licenciement import (
    _ICCP,
    _SANS_ICCP,
    _douze_mois,
    _licenciement,
    _rupture,
    _salarie,
)

pytestmark = pytest.mark.unit


def _calcul(groupe, mois, age=None, reference=4250.0):
    return indemnite_licenciement_metallurgie(
        groupe=groupe, mois_d_anciennete=mois, salaire_reference=reference, age=age
    )


def test_le_cas_de_l_audit_groupe_f_quinze_ans_et_cinq_mois():
    assert _calcul("F", 185, age=42)["montant"] == 27412.50


def test_groupes_a_a_e_le_bareme_de_la_convention_vaut_le_legal():
    # 1/4 jusqu'à 10 ans, 1/3 au-delà : 12 ans = 2,5 + 2/3 de mois.
    assert _calcul("C", 144)["montant"] == round(4250 * (10 / 4 + 2 / 3), 2)


def test_groupe_f_moins_de_huit_ans_un_quart_par_annee():
    assert _calcul("F", 60)["montant"] == round(4250 * 5 / 4, 2)


def test_majoration_de_50_a_54_ans_avec_un_plancher_de_trois_mois():
    # 8 ans : 7/5 + 3/5 = 2 mois ; +20 % = 2,4 ; au moins 3 mois.
    assert _calcul("G", 96, age=52)["mois_de_salaire"] == 3.0
    # 20 ans : 7/5 + 13 × 3/5 = 9,2 ; +20 % = 11,04.
    assert _calcul("G", 240, age=52)["mois_de_salaire"] == pytest.approx(11.04)


def test_majoration_de_55_a_59_ans_et_plafond_de_dix_huit_mois():
    # 10 ans : 7/5 + 3 × 3/5 = 3,2 mois ; +30 % = 4,16 ; au moins 6 mois.
    assert _calcul("H", 120, age=56)["mois_de_salaire"] == 6.0
    # 25 ans : 7/5 + 18 × 3/5 = 12,2 ; +30 % = 15,86.
    assert _calcul("H", 300, age=56)["mois_de_salaire"] == pytest.approx(15.86)
    # 40 ans : 1,4 + 33 × 3/5 = 21,2, plafonné à 18 mois.
    assert _calcul("I", 480, age=57)["mois_de_salaire"] == 18.0


def test_a_partir_de_61_ans_pas_de_minoration_mais_une_alerte():
    resultat = _calcul("F", 185, age=62)
    assert resultat["montant"] == 27412.50
    assert any("75.3.3" in a for a in resultat["alertes"])


def test_moins_de_huit_mois_ou_groupe_inconnu_rien():
    assert _calcul("F", 7) is None
    assert _calcul("", 185) is None


@pytest.mark.parametrize(
    "classification, groupe",
    [({"groupe": "F"}, "F"), ({"niveau_dsn": "11 F"}, "F"), ({"groupe_emploi": "b"}, "B"), ({}, "")],
)
def test_le_groupe_d_emplois_de_la_classification(classification, groupe):
    assert groupe_d_emplois(classification) == groupe


def test_la_rupture_conventionnelle_prend_le_minimum_conventionnel():
    plancher = _calcul("F", 185, age=42)
    rc = calculer_indemnite_rupture_conventionnelle(185 / 12, 4250.0, None, plancher)
    assert rc["montant_minimum"] == 27412.50
    assert rc["montant_negocie"] == 27412.50
    assert rc["minimum_legal"] < 27412.50
    assert "Minimum conventionnel" in rc["calcul"]


def test_une_rupture_au_minimum_legal_est_signalee_sous_le_minimum_conventionnel():
    plancher = _calcul("F", 185, age=42)
    rc = calculer_indemnite_rupture_conventionnelle(185 / 12, 4250.0, 18379.00, plancher)
    assert rc["montant_negocie"] == 18379.00
    assert any("minimum de la convention collective" in a for a in rc["alertes"])


def _cadre_metallurgie(hire_date="2010-10-01"):
    return {
        **_salarie(hire_date),
        "date_naissance": "1984-01-10",
        "classification_conventionnelle": {"idcc": "3248", "groupe": "F", "classe": 11},
    }


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_dossier_de_rupture_d_un_cadre_de_la_metallurgie(_iccp):
    dossier = calculer_indemnites_sortie(_cadre_metallurgie(), _rupture(), _douze_mois())
    rc = dossier["indemnite_rupture_conventionnelle"]
    details = rc["details"]
    # Du 01/10/2010 au 31/10/2026 : 16 ans et 1 mois, soit 193 mois.
    attendu = round(dossier["salaire_reference"] * (7 / 5 + (193 / 12 - 7) * 3 / 5), 2)
    assert details["minimum_conventionnel"] == attendu
    assert rc["montant_minimum"] == rc["montant_negocie"] == attendu
    assert details["minimum_legal"] < attendu


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_licenciement_d_un_cadre_de_la_metallurgie_verse_l_indemnite_conventionnelle(_iccp):
    dossier = calculer_indemnites_sortie(_cadre_metallurgie(), _licenciement(), _douze_mois())
    bloc = dossier["indemnite_licenciement"]
    assert bloc["base_calcul"] == "Conventionnelle"
    assert bloc["montant"] > bloc["montant_legal"]
    assert "Convention de la métallurgie, groupe F" in bloc["calcul"]


@patch(_ICCP, return_value=_SANS_ICCP)
def test_hors_metallurgie_rien_ne_change(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _rupture(), _douze_mois())
    details = dossier["indemnite_rupture_conventionnelle"]["details"]
    assert details["minimum_conventionnel"] is None
    assert details["montant_minimum"] == details["minimum_legal"]
