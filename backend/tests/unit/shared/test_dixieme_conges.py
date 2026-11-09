"""L3141-24 et F33359 : une base commune aux bulletins, sorties et provisions."""
from datetime import date

import pytest

from app.shared.domain.dixieme_conges import (
    calculer_base_dixieme,
    calculer_base_periode,
    montant_dixieme,
    part_reconstituee,
)


def test_exemple_service_public_dix_jours_ouvres():
    assert montant_dixieme(24000.0, 10.0, 25.0) == 960.0
    assert montant_dixieme(24000.0, 12.0, 30.0) == 960.0


def test_maladie_et_complement_employeur_ne_comptent_pas_deux_fois():
    resultat = calculer_base_dixieme(2900.0, [
        {"code": "brut:arret:maladie", "libelle": "Absence maladie", "perte": 1000.0},
        {"code": "brut:maintien_employeur", "libelle": "Maintien de salaire", "gain": 900.0},
    ])
    assert resultat.base == 2800.0
    assert resultat.reconstitution == 800.0
    assert resultat.complement_remplace == 900.0


@pytest.mark.parametrize("libelle", [
    "Absence accident du travail", "Absence maladie professionnelle",
    "Absence accident de trajet", "Absence maternité", "Absence paternité", "Absence adoption",
])
def test_absences_assimilees_en_entier(libelle):
    assert calculer_base_dixieme(2000.0, [{"libelle": libelle, "perte": 1000.0}]).base == 3000.0


def test_un_accident_non_professionnel_n_est_pas_un_accident_du_travail():
    assert part_reconstituee("Absence accident non professionnel") == 0.8


def test_mi_temps_therapeutique_sans_suspension_ni_reconstitution_a_80():
    assert part_reconstituee("Absence mi-temps thérapeutique") == 0.0
    assert calculer_base_dixieme(1500.0, [{"libelle": "Absence mi-temps thérapeutique", "perte": 1500.0}]).base == 1500.0


def test_activite_partielle_reconstitue_le_salaire_normal():
    assert calculer_base_dixieme(1800.0, [{"libelle": "Absence activité partielle", "perte": 1200.0}]).base == 3000.0


@pytest.mark.parametrize("libelle", [
    "Ind.Conv départ en retraite",
    "B_DY INDEMNITE DEPART A LA RETRAITE",
    "Indemnité conventionnelle de licenciement",
    "Indemnité spéciale de licenciement",
    "Indemnité de rupture conventionnelle",
    "Indemnité de mise à la retraite",
])
def test_les_indemnites_de_rupture_sortent_de_la_base(libelle):
    assert calculer_base_dixieme(15000.0, [{"libelle": libelle, "gain": 12000.0}]).base == 3000.0


def test_le_preavis_paye_reste_dans_la_base():
    assert calculer_base_dixieme(5000.0, [
        {"libelle": "Indemnité compensatrice de préavis de licenciement", "gain": 2000.0},
    ]).base == 5000.0


def test_primes_exclues_et_gratification_discretionnaire():
    resultat = calculer_base_dixieme(4200.0, [
        {"libelle": "Prime de fin d'année", "gain": 1000.0},
        {"libelle": "Prime de bilan", "gain": 200.0},
        {"libelle": "Prime exceptionnelle", "gain": 300.0},
    ])
    assert resultat.base == 3000.0  # le seul libellé « exceptionnelle » ne prouve pas une gratification
    assert any("exceptionnelle" in a for a in resultat.alertes)
    assert calculer_base_dixieme(3300.0, [
        {"libelle": "Prime exceptionnelle", "gain": 300.0, "gratification_discretionnaire": True},
    ]).base == 3000.0


@pytest.mark.parametrize("code,gain,perte,attendu", [
    ("brut:retenue_absence_integrale", 100.0, None, 2400.0),
    ("brut:retenue_absence_mois_complet", 100.0, None, 2400.0),
    ("brut:complement_absence_integrale", None, 100.0, 2560.0),
    ("brut:reduction_hs_absence", None, 100.0, 2560.0),
    ("brut:absence_ferie_non_paye:jour", None, 100.0, 2480.0),
])
def test_retenues_annexes_par_code_stable_meme_apres_renommage(code, gain, perte, attendu):
    resultat = calculer_base_dixieme(800.0, [
        {"code": "brut:absence_maladie:jour", "libelle": "Absence maladie", "perte": 2100.0},
        {"code": code, "libelle": "Libellé modifié", "gain": gain, "perte": perte},
    ])
    assert resultat.base == attendu


def test_un_maintien_sans_absence_correspondante_ne_se_soustrait_pas():
    resultat = calculer_base_dixieme(3000.0, [{"libelle": "Rappel maintien de salaire", "gain": 500.0}])
    assert resultat.base == 3000.0
    assert resultat.alertes


def test_regul_salaire_ambigue_signalee_sans_inventer_son_affectation():
    resultat = calculer_base_dixieme(3500.0, [{"libelle": "Régul salaire", "gain": 500.0}])
    assert resultat.base == 3500.0
    assert any("régularisation" in a.lower() for a in resultat.alertes)


def test_deux_contrats_dans_un_meme_mois_s_additionnent():
    resultat = calculer_base_periode([
        {"annee": 2026, "mois": 9, "brut": 1000.0, "lignes": []},
        {"annee": 2026, "mois": 9, "brut": 1500.0, "lignes": []},
    ], debut=date(2026, 9, 1), fin=date(2026, 9, 30))
    assert resultat.base == 2500.0


def test_un_mois_absent_ne_devient_pas_un_salaire_nul():
    resultat = calculer_base_periode([
        {"annee": 2026, "mois": 6, "brut": 2000.0, "lignes": []},
    ], debut=date(2026, 6, 1), fin=date(2026, 7, 31))
    assert resultat.base is None
    assert any("07/2026" in a for a in resultat.alertes)


def test_un_cumul_repris_complete_la_remuneration_sans_etre_modifie():
    resultat = calculer_base_periode([
        {"annee": 2026, "mois": 6, "brut": 1000.0, "lignes": [
            {"libelle": "Absence maladie", "perte": 1000.0},
        ]},
    ], debut=date(2026, 6, 1), fin=date(2026, 7, 31), brut_repris=3000.0)
    assert resultat.base == 3800.0
    assert resultat.alertes  # la rémunération est connue, les lignes du mois manquant ne le sont pas


def test_mois_hors_periode_ignores_et_changement_au_premier_juin():
    bulletins = [
        {"annee": 2026, "mois": 5, "brut": 2000.0, "lignes": []},
        {"annee": 2026, "mois": 6, "brut": 3000.0, "lignes": []},
    ]
    assert calculer_base_periode(bulletins, debut=date(2026, 5, 1), fin=date(2026, 5, 31)).base == 2000.0
    assert calculer_base_periode(bulletins, debut=date(2026, 6, 1), fin=date(2026, 6, 30)).base == 3000.0


def test_dixieme_inconnu_sans_base_ou_droits():
    assert montant_dixieme(None, 10.0, 25.0) is None
    assert montant_dixieme(24000.0, 10.0, 0.0) is None
