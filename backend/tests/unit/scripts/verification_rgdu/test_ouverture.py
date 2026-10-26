"""Tâche 10 recalée : ouverture au 30/09 (R1) et lecture d'un bulletin d'octobre à blanc.

Montants anonymisés tirés de cas réels (salarié A : 39 h ; salarié B : arrêt sans maintien).
"""
import pytest

from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee
from scripts.verification_rgdu.ouverture import (
    base_de_la_reduction,
    decomposer,
    ecart_d_ouverture,
    elements_martine,
    heures_qui_redonnent_quadra,
    smic_loi_martine,
)

pytestmark = pytest.mark.unit
P = Parametres()


def test_une_ouverture_coherente_n_a_pas_d_ecart():
    r = reduction_cumulee(14349.67, round(998.6 * 12.02, 2), P)
    assert abs(ecart_d_ouverture(14349.67, 998.6, r, P)) < 1.0
    # Palier d'arrondi du coefficient : environ 0,15 h sur ce brut.
    assert abs(heures_qui_redonnent_quadra(14349.67, r, P) - 998.6) < 0.2


def test_des_heures_imprimees_trop_basses_donnent_un_ecart_negatif():
    r = reduction_cumulee(14349.67, round(998.6 * 12.02, 2), P)
    assert ecart_d_ouverture(14349.67, 973.8, r, P) < -200


def test_la_base_lue_est_celle_du_moteur_brut_de_l_annee_et_reprise_retiree():
    cumuls = {"cumuls": {"brut_total": 14600.48, "heures_remunerees": 714.5,
                         "reduction_generale_patronale": -2761.09,
                         "brut_hors_reduction_generale": 2474.46, "heures_hors_reduction_generale": -99.36}}
    assert base_de_la_reduction(cumuls) == (12126.02, 813.86, 2761.09)
    cumuls["cumuls"]["brut_annee_civile"] = 15000.0
    assert base_de_la_reduction(cumuls)[0] == 12525.54
    assert base_de_la_reduction({"cumuls": {"heures_remunerees": 5.0, "heures_hors_reduction_generale": 9.0,
                                            "brut_total": 10.0, "brut_hors_reduction_generale": 20.0}})[:2] == (0.0, 0.0)


def test_la_reduction_du_mois_se_decompose_sans_reste():
    d = decomposer(20000.0, 1352.0, 4000.0, 2231.48, 169.0, P)
    assert round(d["mois_isole"] + d["effet_du_cumul"] + d["ecart_d_ouverture"], 2) == d["total"]
    due = reduction_cumulee(22231.48, round(1521.0 * 12.02, 2), P)
    assert d["total"] == round(due - 4000.0, 2)


def test_une_ouverture_juste_ne_laisse_que_l_effet_legal_du_cumul():
    deja = reduction_cumulee(20000.0, round(1352.0 * 12.02, 2), P)
    d = decomposer(20000.0, 1352.0, deja, 2231.48, 169.0, P)
    assert d["ecart_d_ouverture"] == 0.0


def _bulletin(absences=(), maintien=None, hs=None):
    brut = [{"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.874, "gain": 1952.6},
            {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "gain": 278.88},
            {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 169.0, "gain": 2231.48},
            {"libelle": "Prime d'ancienneté (23 ans, 12 %)", "quantite": 2231.48, "gain": 267.78},
            {"libelle": "Rappel maintien de salaire août-septembre 2026", "gain": 404.8}]
    if maintien:
        brut.append({"libelle": "Maintien de salaire", "gain": maintien})
    if hs:
        brut.append({"libelle": "Heures supplémentaires à 25 %", "quantite": hs, "gain": round(hs * 16.09, 2)})
    return {"calcul_du_brut": brut, "details_absences": list(absences)}


def test_mois_complet_39_heures_au_smic_de_la_loi():
    el = elements_martine(_bulletin(hs=6.0))
    assert el.rappels == [("Rappel maintien de salaire août-septembre 2026", 404.8)]
    assert smic_loi_martine(el) == round(1823.03 + 17.33 * 12.02 + 6.0 * 12.02, 2)


def test_arret_sans_maintien_au_rapport_des_salaires_salarie_b():
    arret = [{"libelle": "Absence arrêt maladie du 02/10 au 12/10", "quantite": 49.0, "perte": 630.83,
              "is_arret_maladie": True},
             {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 5.6, "perte": 90.12,
              "is_reduction_hs": True}]
    el = elements_martine(_bulletin(arret))
    assert el.retenues == 720.95 and el.retenues_arret == 630.83
    # Le moteur retient 114,4 h × 12,02 = 1 375,09 € ; la loi part de 1 823,03 € et non de
    # 12,02 × 151,67 = 1 823,07 € (tolérance du BOSS, § 630) : 0,04 € d'écart au plus.
    assert abs(smic_loi_martine(el) - 1375.09) <= 0.05


def test_arret_maintenu_en_entier_garde_le_smic_complet():
    arret = [{"libelle": "Absence arrêt maladie du 02/10 au 12/10", "quantite": 49.0, "perte": 630.83,
              "is_arret_maladie": True}]
    assert smic_loi_martine(elements_martine(_bulletin(arret, maintien=630.83))) == 2031.34


def test_conges_payes_pris_ne_reduisent_rien():
    cp = [{"libelle": "Absence congés payés du 05/10 au 09/10", "quantite": 39.0, "perte": 502.09},
          {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 4.0, "perte": 64.37,
           "is_reduction_hs": True}]
    assert smic_loi_martine(elements_martine(_bulletin(cp))) == 2031.34


def test_un_rappel_de_maintien_retablit_le_smic_de_sa_part_de_salaire_boss_800():
    from scripts.verification_rgdu.ouverture import smic_des_rappels_de_maintien

    el = elements_martine(_bulletin())
    # 404,80 € de rappel sur un mois complet de 2 231,48 € : 2 031,34 × 404,80 / 2 231,48.
    assert smic_des_rappels_de_maintien(el) == round(2031.34 * 404.8 / 2231.48, 2)
    el.rappels = [("Rappel prime de juin", 100.0)]
    assert smic_des_rappels_de_maintien(el) == 0.0


def test_forfait_216_jours_mois_complet_et_rappel():
    from scripts.verification_rgdu.ouverture import smic_mois_complet

    pd = {"calcul_du_brut": [{"libelle": "Salaire de base (forfait jour)", "gain": 3750.0}]}
    el = elements_martine(pd, forfait_jours=216)
    assert smic_mois_complet(el) == 1806.3 and smic_loi_martine(el) == 1806.3


def _bulletin_octobre(**k):
    o = {"societe": "colorplast", "ini": "A.", "employee_id": "e1", "generable": None, "smic_rappels_maintien": 0.0,
         "smic_martine": 2031.38, "smic_loi": 2031.34, "reduction_mois": 600.0, "alertes": [],
         "decomposition": {"mois_isole": 600.0, "effet_du_cumul": 0.0, "ecart_d_ouverture": 0.0, "total": 600.0}}
    o.update(k)
    return o


def test_un_bulletin_juste_n_a_aucune_anomalie():
    from scripts.verification_rgdu.ouverture import anomalies_d_un_bulletin

    assert anomalies_d_un_bulletin(_bulletin_octobre(), {"formule_brut": 20000.0}) == []


def test_les_anomalies_d_octobre_sont_classees():
    from scripts.verification_rgdu.ouverture import anomalies_d_un_bulletin

    o = _bulletin_octobre(generable="PayslipBadRequestError: Il manque aussi : Date de naissance.",
                          smic_rappels_maintien=368.49,
                          decomposition={"mois_isole": 600.0, "effet_du_cumul": 0.0, "ecart_d_ouverture": -174.92,
                                         "total": 425.08})
    classes = [c for c, _ in anomalies_d_un_bulletin(o, {"formule_brut": 22032.19, "heures_quadra": 1528.4,
                                                         "base_heures": 1510.1})]
    assert classes == ["donnée à corriger", "donnée à corriger", "défaut de Martine"]


def test_un_ecart_d_ouverture_sous_un_palier_du_coefficient_est_un_arrondi():
    from scripts.verification_rgdu.ouverture import anomalies_d_un_bulletin

    o = _bulletin_octobre(decomposition={"mois_isole": 177.0, "effet_du_cumul": 0.0, "ecart_d_ouverture": -1.18,
                                         "total": 175.8})
    assert anomalies_d_un_bulletin(o, {"formule_brut": 35133.79}) == []
