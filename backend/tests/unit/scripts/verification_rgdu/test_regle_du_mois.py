"""SMIC légal du mois à partir d'un bulletin Quadra (regles.md, R-H1 à R-H12, R-A2, R-F2).

Chaque test cite l'ID de sa règle. Les montants viennent de regles.md quand il en donne
(1 823,03 ; 1 806,30 ; l'exemple de la fiche 2681 adapté au SMIC 2026), sinon de lignes
réelles de bulletins Quadra, anonymisées (« salarié A », « salarié B »…), dont la DSN de
Quadra donne la valeur de contrôle.
"""
from decimal import ROUND_HALF_UP, Decimal

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.verification_rgdu.quadra_mois import MoisQuadra
from scripts.verification_rgdu.regle_du_mois import (
    SmicLoi, choisir_reference, elements_loi, smic_loi_du_mois,
)

pytestmark = pytest.mark.unit

SMIC_39H = 2031.34   # 1 823,03 + 17,33 × 12,02, arrondi (R-H1)


def _attendu(r, occasionnelles=0.0):
    """regles.md, « Détails utiles », R-H3 : SMIC = 1 823,03 × r + heures structurelles ×
    12,02 × r + heures occasionnelles × 12,02, arrondi au centime demi au supérieur."""
    brut = 1823.03 * r + 17.33 * 12.02 * r + occasionnelles * 12.02
    return float(Decimal(repr(brut)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _g(libelle, base=None, taux=None, gain=None):
    return Ligne(None, libelle, base=base, taux=taux, gain=gain)


def _r(libelle, base=None, taux=None, montant=None):
    return Ligne(None, libelle, base=base, taux=taux, montant_sal=montant)


def _i(libelle):
    return Ligne(None, libelle)


def _b(*lignes):
    return Bulletin("ESSAI", lignes=[*lignes, _g("SALAIRE BRUT", gain=1.0)])


def _mq(mois=3, entree=None, sortie=None, forfait=None, preavis=None):
    m = MoisQuadra("essai", mois, "ESSAI", "1999999999999", 0.0, 0.0, 0.0, 0.0, 0.0)
    m.entree, m.sortie, m.forfait_jours, m.indemnite_preavis = entree, sortie, forfait, preavis
    return m


def _base_39h(taux=12.9492, taux_hs=16.1865):
    """Salaire de base d'un 39 h : 151,67 h + 17,33 h structurelles (salarié B, réel)."""
    return (_g("SALAIRE DE BASE", 151.67, taux, round(151.67 * taux, 2)),
            _g("H. supp majorées à 25 %", 17.33, taux_hs, round(17.33 * taux_hs, 2)),
            _g("SOUS TOTAL SALAIRE DE BASE", 169.0, None, round(151.67 * taux, 2) + round(17.33 * taux_hs, 2)))


# --- R-H1 : mois complet -------------------------------------------------------------

def test_r_h1_mois_complet_35_heures_vaut_1823_03():
    b = _b(_g("SALAIRE DE BASE", 151.67, 12.02, 1823.07))
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == 1823.03 and res.smic_variante is None and "R-H1" in res.regle


def test_r_h1_salarie_a_janvier_redonne_le_smic_de_la_dsn_2277_75():
    """Salarié A, Colorplast, janvier : 17,33 h structurelles, 12 + 8,5 h occasionnelles, un
    jour de congé payé. La DSN de Quadra déclare 2 277,75 € ; sans absence ni autre élément,
    la loi donne la même valeur : 1 823,03 + (17,33 + 20,5) × 12,02."""
    b = _b(
        _g("Congés payés : 020126", 1.0, 112.0, 112.0),
        _r("H.Absence Congés Payés", 7.0, 14.0, 98.0),
        _r("H. supp majorées à 25 %", 0.8, 17.5, 14.0),
        _g("SALAIRE DE BASE", 151.67, 14.0, 2123.38),
        _g("H. supp majorées à 25 %", 17.33, 17.5, 303.28),
        _g("SOUS TOTAL SALAIRE DE BASE", 169.0, None, 2426.66),
        _g("Heures supplémentaires 25", 12.0, 17.5, 210.0),
        _g("Heures supplémentaires 50", 8.5, 21.0, 178.5),
        _g("Prime exceptionnelle", 150.0, None, 150.0),
        _g("Prime ancienneté", 1941.33, 3.0, 58.24),
        _g("ARBITRAGE DES CONGES PAYES", 112.0, None, 112.0),
    )
    assert smic_loi_du_mois(_mq(1), elements_loi(b)).smic == 2277.75


# --- R-H2 : congés payés pris ---------------------------------------------------------

def test_r_h2_conges_payes_pris_ne_baissent_pas_le_smic():
    b = _b(
        _g("Congés payés : 050326-060326", 2.0, 103.59, 207.18),
        _r("H.Absence Congés Payés", 14.0, 12.9492, 181.29),
        _r("H. supp majorées à 25 %", 1.6, 16.1865, 25.9),
        *_base_39h(),
    )
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == SMIC_39H and "R-H2" in res.regle


# --- R-H3 : absence non payée, rapport des salaires ------------------------------------

def test_r_h3_exemple_de_la_fiche_2681_adapte_au_smic_2026():
    """regles.md, « Détails utiles » : 39 h, 10 heures supplémentaires occasionnelles, deux
    semaines d'absence non payée, rapport 1 230,73 / 2 285,65 ;
    SMIC = 1 823,03 × r + (10 + 17,33 × r) × 12,02 = 1 213,99 (r non arrondi)."""
    b = _b(
        _g("SALAIRE DE BASE", 151.67, 13.0, 1971.71),
        _g("H. supp majorées à 25 %", 17.33, 18.1154, 313.94),
        _g("Heures supplémentaires 25", 10.0, 18.1154, 181.15),
        _r("Abs. Congés s.so 020326-130326", 70.0, 13.0, 910.0),
        _r("H. supp majorées à 25 %", 8.0, 18.1154, 144.92),
    )
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == 1213.99 and "R-H3" in res.regle


def test_r_h3_retenue_valorisee_sur_151_67_revient_a_la_soustraction():
    """Salarié B, janvier : 3,14 h d'absence non payée à 12,9492 €, 0,36 h structurelles
    retirées. Rapport (2 244,51 − 40,66 − 5,83) / 2 244,51 ; SMIC 2 031,34 × r = 1 989,26,
    soit 2 031,34 − (3,14 + 0,36) × 12,02 au centime près (regles.md, R-H3)."""
    b = _b(*_base_39h(), _r("Abs. Abs aut nonpayé 210126", 3.14, 12.9492, 40.66),
           _r("H. supp majorées à 25 %", 0.36, 16.1865, 5.83), _g("Prime exceptionnelle", 100.0, None, 100.0))
    res = smic_loi_du_mois(_mq(1), elements_loi(b))
    assert res.smic == 1989.26
    assert abs(res.smic - round(SMIC_39H - 3.5 * 12.02, 2)) <= 0.03


def test_r_h3_une_retenue_autre_entre_aussi_dans_le_rapport():
    """« Absence pour entrée ou sortie » sans entrée ni sortie dans le mois (retour d'une
    longue absence, vu à Mont-Blanc) : toutes les retenues d'absence entrent dans le rapport."""
    b = _b(_r("Absence pour entrée ou sortie", 14.0, 12.02, 168.28), _g("SALAIRE DE BASE", 151.67, 12.02, 1823.07))
    res = smic_loi_du_mois(_mq(1), elements_loi(b))
    assert res.smic == round(1823.03 * (1823.07 - 168.28) / 1823.07, 2)
    assert "entrée ou sortie" in res.note


# --- R-H4 : arrêt maladie ------------------------------------------------------------

def test_r_h4_aucun_maintien_sur_un_mois_entier_donne_un_smic_nul():
    b = _b(*_base_39h(15.5126, 19.3908), _r("Absence maladie 010526-310526", 151.67, 15.5126, 2352.8),
           _r("H. supp majorées à 25 %", 17.33, 19.3908, 336.04))
    res = smic_loi_du_mois(_mq(5), elements_loi(b))
    assert res.smic == 0.0 and res.smic_variante is None and "R-H4" in res.regle


def test_r_h4_maintien_integral_du_brut_garde_le_smic_entier():
    b = _b(*_base_39h(), _r("Absence maladie 090326-110326", 21.0, 12.9492, 271.93),
           _r("H. supp majorées à 25 %", 2.4, 16.1865, 38.85), _g("Maintien de salaire", 310.78, None, 310.78))
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == SMIC_39H and res.smic_variante is None


def test_r_h4_maintien_partiel_lu_sur_le_bulletin_une_seule_lecture():
    """Une ligne d'information porte le taux (« = 80% ») : maintien partiel, rapport des
    salaires seul (R-H4, 5e alinéa) — pas de point non tranché."""
    b = _b(*_base_39h(), _r("Absence maladie 090326-130326", 35.0, 12.9492, 453.22),
           _r("H. supp majorées à 25 %", 4.0, 16.1865, 64.75), _g("Maintien de salaire", 362.0, None, 362.0),
           _i("le 09-03 au 13-03 = 80%"))
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    r = (2244.51 - 453.22 - 64.75 + 362.0) / 2244.51
    assert res.smic == _attendu(r) and res.smic_variante is None
    assert "80" in res.note


def test_point_non_tranche_1_maintien_sans_ijss_porte_deux_lectures():
    """Salarié C, mars (réel) : arrêt de 70 h, 8,1 h structurelles retirées, 0,9 h d'absence
    non payée, maintien 310,78, aucune ligne d'IJSS. Maintien intégral (sous déduction des
    IJSS) ou partiel : indiscernable. Lecture principale « rapport_salaires » ; variante
    « smic_entier » : l'arrêt compte comme payé, l'absence non payée reste retenue."""
    b = _b(
        _g("Congés payés : 020326", 1.0, 103.59, 103.59),
        _r("H.Absence Congés Payés", 7.0, 12.9492, 90.64),
        _r("H. supp majorées à 25 %", 0.8, 16.1865, 12.95),
        *_base_39h(),
        _r("Abs. Abs aut nonpayé 260226", 0.9, 12.9492, 11.65),
        _r("Absence maladie 160326-280326", 70.0, 12.9492, 906.44),
        _r("H. supp majorées à 25 %", 8.1, 16.1865, 131.11),
        _g("Maintien de salaire", 310.78, None, 310.78),
    )
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.variante == "point_1_subrogation"
    assert res.smic == 1363.05                                   # 2 031,34 × 1 506,09 / 2 244,51
    hs_non_payee = 131.11 * 0.9 / 70.9
    r_variante = (2244.51 - 11.65 - hs_non_payee) / 2244.51
    assert res.smic_variante == _attendu(r_variante)
    assert "point n° 1" in res.note and "absence" in res.note


def test_point_non_tranche_1_sortie_en_cours_de_mois_calcule_les_deux_lectures():
    """Point n° 1 × sortie : jamais un chiffre unique (addendum du contrôleur)."""
    b = _b(*_base_39h(), _r("Absence pour entrée ou sortie", 35.0, 12.9492, 453.22),
           _r("Absence maladie 020326-060326", 35.0, 12.9492, 453.22),
           _r("H. supp majorées à 25 %", 8.0, 16.1865, 129.49), _g("Maintien de salaire", 200.0, None, 200.0))
    res = smic_loi_du_mois(_mq(3, sortie="20/03/2026"), elements_loi(b))
    assert res.variante == "point_1_subrogation"
    assert res.smic is not None and res.smic_variante is not None and res.smic_variante > res.smic
    assert "sortie" in res.note


# --- R-H5 : absences payées par l'employeur -------------------------------------------

def test_r_h5_evenement_familial_maintenu_garde_le_smic_complet():
    b = _b(*_base_39h(), _r("Abs. Evt familli 250226-270226", 21.0, 12.9492, 271.93),
           _r("H. supp majorées à 25 %", 2.4, 16.1865, 38.85), _g("Maintien de salaire", 310.78, None, 310.78))
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == SMIC_39H and "R-H5" in res.regle


def test_r_h5_paternite_sans_maintien_au_forfait_redonne_la_dsn_1642_09():
    """Salarié D, Comitech, janvier : forfait 216 jours, 2 jours de paternité retenus sans
    maintien. Rapport 3 409,09 / 3 750 sur 1 806,30 = 1 642,09, valeur de la DSN de Quadra."""
    b = _b(_g("SALAIRE DE BASE", None, None, 3750.0), _r("Abs. paternité 010126-040126", 2.0, 170.4545, 340.91),
           _i("Forfait 216 jours"))
    res = smic_loi_du_mois(_mq(1, forfait=216), elements_loi(b))
    assert res.smic == 1642.09 and res.smic_variante is None


# --- R-H6 : jour férié chômé non payé ---------------------------------------------------

def test_r_h6_jour_ferie_non_paye_au_rapport_des_salaires():
    b = _b(*_base_39h(12.954, 16.1925), _r("Abs. JF non payé 080526", 7.0, 12.954, 90.68),
           _r("H. supp majorées à 25 %", 0.8, 16.1925, 12.95))
    res = smic_loi_du_mois(_mq(5), elements_loi(b))
    full = round(151.67 * 12.954, 2) + round(17.33 * 16.1925, 2)
    assert res.smic == _attendu((full - 90.68 - 12.95) / full) and "R-H6" in res.regle


# --- R-H7 : entrée ou sortie en cours de mois --------------------------------------------

def test_r_h7_entree_avec_ligne_absence_pour_entree_ou_sortie():
    """Salarié E, Colorplast, avril (réel) : entrée le 7, 30,5 h retenues, 5 h
    occasionnelles. Rapport 1 742,55 / 2 114,65 ; la DSN de Quadra déclare 1 733,99."""
    b = _b(_g("SALAIRE DE BASE", 151.67, 12.2, 1850.37), _g("H. supp majorées à 25 %", 17.33, 15.25, 264.28),
           _g("Heures supplémentaires 25", 5.0, 15.25, 76.25),
           _r("Absence pour entrée ou sortie", 30.5, 12.2, 372.1))
    res = smic_loi_du_mois(_mq(4, entree="07/04/2026"), elements_loi(b))
    assert res.smic == 1734.0 and "R-H7" in res.regle


def test_r_h7_salaire_de_base_proratise_se_rapporte_au_mois_complet_du_contrat():
    """Salarié F, Comitech, janvier (réel) : entrée le 19, salaire de base payé sur 70 h et
    8 h structurelles. Le mois complet vient d'un autre mois du contrat (151,67 h, 17,33 h),
    valorisé au taux du mois : rapport 1 016 / 2 201,32 = 0,4615 ; SMIC 937,54."""
    b = _b(_i("ENTREE LE 19/01/2026"), _g("SALAIRE DE BASE", 70.0, 12.7, 889.0),
           _g("H. supp majorées à 25 %", 8.0, 15.875, 127.0), _g("Prime exceptionnelle", 325.0, None, 325.0))
    ref = elements_loi(_b(_g("SALAIRE DE BASE", 151.67, 12.7, 1926.21),
                          _g("H. supp majorées à 25 %", 17.33, 15.875, 275.11)))
    res = smic_loi_du_mois(_mq(1, entree="19/01/2026"), elements_loi(b), ref)
    assert res.smic == 937.54


def test_r_h7_salaire_proratise_sans_autre_mois_du_contrat_n_est_pas_devine():
    b = _b(_g("SALAIRE DE BASE 5 au 26/01", 112.0, 12.8505, 1439.26))
    res = smic_loi_du_mois(_mq(1, entree="05/01/2026", sortie="26/01/2026"), elements_loi(b))
    assert res.smic is None and "mois complet inconnu" in res.note


def test_r_h7_entree_le_premier_du_mois_compte_un_smic_entier():
    b = _b(*_base_39h())
    assert smic_loi_du_mois(_mq(3, entree="01/03/2026"), elements_loi(b)).smic == SMIC_39H


def test_r_a2_d_aucun_jour_de_contrat_dans_le_mois_aucun_smic():
    b = _b(*_base_39h())
    res = smic_loi_du_mois(_mq(3, sortie="27/02/2026"), elements_loi(b))
    assert res.smic is None and "aucun jour de contrat" in res.note


def test_point_non_tranche_4_preavis_deux_lectures():
    b = _b(*_base_39h(), _r("Absence pour entrée ou sortie", 70.0, 12.9492, 906.44),
           _r("H. supp majorées à 25 %", 8.0, 16.1865, 129.49), _g("Indemnité compensatrice de préavis", None, None, 1100.0))
    res = smic_loi_du_mois(_mq(3, sortie="13/03/2026", preavis=1100.0), elements_loi(b))
    assert res.variante == "point_4_preavis" and res.smic_variante == SMIC_39H
    assert res.smic < res.smic_variante


# --- Bulletin sans salaire du mois ----------------------------------------------------

def test_bulletin_de_participation_seule_n_a_pas_de_smic():
    b = _b(_r("CSG déductible à l'IR", 221.81, 6.8, 15.08), _g("Participation 2025", 221.81, None, 221.81))
    res = smic_loi_du_mois(_mq(5, entree="01/05/2026", sortie="01/05/2026"), elements_loi(b))
    assert res.smic is None and res.note == "bulletin sans salaire du mois"


# --- R-H8 à R-H12 ----------------------------------------------------------------------

def test_r_h8_temps_partiel_12_02_par_heure_du_contrat():
    b = _b(_g("SALAIRE DE BASE", 87.0, 12.5, 1087.5))
    res = smic_loi_du_mois(_mq(), elements_loi(b))
    assert res.smic == round(12.02 * 87.0, 2) and "R-H8" in res.regle


def test_r_h9_forfait_216_jours_vaut_1806_30():
    b = _b(_g("SALAIRE DE BASE", None, None, 3235.0), _i("Forfait 216 jours"))
    res = smic_loi_du_mois(_mq(2, forfait=216), elements_loi(b))
    assert res.smic == 1806.30 and "R-H9" in res.regle


def test_r_h10_apprenti_paye_sous_le_smic_garde_le_smic_entier():
    b = _b(_g("SALAIRE DE BASE", 151.67, 6.37, 966.14))
    assert smic_loi_du_mois(_mq(), elements_loi(b)).smic == 1823.03


def test_r_h12_primes_et_indemnites_n_ajoutent_pas_de_smic():
    b = _b(*_base_39h(), _g("Prime ancienneté", 1941.33, 3.0, 58.24), _g("Prime poste difficile", 30.0, None, 30.0),
           _g("Ind.de précarité des CDD", 797.04, 100.0, 797.04), _g("Ind.de CP des CDD", 940.23, 100.0, 940.23))
    assert smic_loi_du_mois(_mq(), elements_loi(b)).smic == SMIC_39H


# --- R-F2 : juin -------------------------------------------------------------------------

def test_r_f2_juin_reste_a_12_02_et_signale_la_tolerance_des_contrats_finis_en_juin():
    b = _b(*_base_39h())
    res = smic_loi_du_mois(_mq(6, sortie="30/06/2026"), elements_loi(b))
    assert res.smic == SMIC_39H and "tolérance" in res.note


# --- Lecture du bulletin et choix du mois de référence ------------------------------------

def test_elements_loi_classe_les_lignes_du_bulletin():
    b = _b(
        _r("H.Absence Congés Payés", 7.0, 12.0, 84.0),
        _r("H. supp majorées à 25 %", 0.8, 15.0, 12.0),
        _g("SALAIRE DE BASE", 151.67, 12.0, 1820.04),
        _g("H. supp majorées à 25 %", 17.33, 15.0, 259.95),
        _g("Heures supplémentaires 50", 4.0, 18.0, 72.0),
        _r("Prol.rechute 240426-300426", 35.0, 12.0, 420.0),
        _r("Tps.part.théra.150626-300626", 40.06, 12.0, 480.72),
        _r("H. supp majorées à 25 %", 8.6, 15.0, 129.0),
        _g("Rappel Maintien de salaire", 100.0, None, 100.0),
        _g("Maintien de salaire", 50.0, None, 50.0),
        _g("Ind.Complem.prevoyance salarié", 918.78, None, 918.78),
        _i("le 27 et 28-01=100%"),
        _r("Report NAP négatif", None, None, 12.0),
    )
    el = elements_loi(b)
    assert el.salaire_base == 1820.04 and el.heures_base == 151.67
    assert el.heures_structurelles == 17.33 and el.heures_occasionnelles == 4.0
    assert [r.nature for r in el.retenues] == ["maladie", "maladie", "heures_sup"]
    assert el.retenues[2].arret == pytest.approx(129.0)          # HS retirées rattachées à l'arrêt
    assert el.maintien == 150.0 and el.rappel_maintien and el.ij_complementaires == 918.78
    assert el.taux_maintien_lus == [100]


def test_choisir_reference_prend_le_mois_normal_le_plus_proche():
    normal = elements_loi(_b(_g("SALAIRE DE BASE", 151.67, 12.0, 1820.04)))
    prorata = elements_loi(_b(_g("SALAIRE DE BASE", 70.0, 12.0, 840.0)))
    mois = {1: (_mq(1, entree="19/01/2026"), prorata), 2: (_mq(2), normal), 5: (_mq(5), normal)}
    assert choisir_reference(mois, 1) is normal
    assert choisir_reference({1: mois[1]}, 1) is None
    assert isinstance(SmicLoi(None), SmicLoi)
