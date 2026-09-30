"""SMIC de référence du mois : une règle, un cas, une source (docs/reference/reduction-generale-2026/regles.md).

Les valeurs attendues sont écrites en dur, calculées à la main depuis regles.md ou reprises
des exemples publiés par net-entreprises (fiche 2681, SMIC 2024 à 11,65 €/h), pour que le
test ne recopie pas la formule qu'il vérifie.
"""
from datetime import date

import pytest

from scripts.verification_rgdu.oracle_smic import (
    SMIC_H_2026,
    mois_incomplet,
    rapport_des_salaires,
    smic_au_rapport_des_salaires,
    smic_entree_sortie,
    smic_forfait_jours,
    smic_maintien_subroge,
    smic_mensuel,
    smic_mois_complet,
)

pytestmark = pytest.mark.unit

SMIC_H_2024 = 11.65          # SMIC des exemples de la fiche net-entreprises 2681
SMIC_DU_MOIS_2026 = 1823.03  # 12,02 × 1 820 / 12 arrondi (choix de calcul n° 1)
FORFAIT_216 = 1806.30        # 1 823,03 × 216 / 218 (R-H9)


def test_r_f2_smic_de_reference_fige_a_12_02_toute_l_annee():
    """R-F2 : 12,02 €/h pour tout 2026, même après la hausse du 1er juin (12,31 €)."""
    assert SMIC_H_2026 == 12.02
    assert smic_mensuel() == SMIC_DU_MOIS_2026
    assert smic_mensuel(12.31) == 1867.02          # ce que donnerait juin sans le gel


def test_choix_1_base_mensuelle_1823_03_et_non_la_tolerance_1823_07():
    """Choix de calcul n° 1 (R-H1) : 12,02 × 1 820 / 12 arrondi, pas 12,02 × 151,67 = 1 823,07.
    Seule vérification du mois complet sans heures : les autres tests s'y fient."""
    assert smic_mois_complet(151.67, 0.0, 0.0) == SMIC_DU_MOIS_2026
    assert round(12.02 * 151.67, 2) == 1823.07


def test_r_h1_mois_complet_avec_heures_sup_comme_quadra_en_dsn():
    """R-H1 : salarié A, janvier 2026 : 1 823,03 + 37,83 h × 12,02 = 2 277,75 (DSN S21.G00.79 type 01)."""
    assert smic_mois_complet(151.67, 37.83, 0.0) == 2277.75


def test_r_h1_la_duree_du_contrat_se_donne_hors_heures_supplementaires():
    """R-H1 : 169 h (39 h) n'est pas une durée de contrat : 151,67 h + 17,33 h structurelles.
    Refuser 169 évite de perdre en silence les heures structurelles."""
    with pytest.raises(ValueError):
        smic_mois_complet(169.0, 0.0, 0.0)
    assert smic_mois_complet(151.67, 17.33, 0.0) == 2031.34


def test_r_h2_conges_payes_indemnite_au_dixieme_sans_smic_en_plus():
    """R-H2 : congés payés pris, SMIC du mois complet ; une indemnité au dixième supérieure au
    maintien n'ajoute pas de SMIC (le rapport est plafonné à 1, choix n° 3)."""
    assert smic_au_rapport_des_salaires(151.67, 2150.0, 2000.0) == SMIC_DU_MOIS_2026


def test_r_h3_absence_non_payee_au_rapport_des_salaires_exemple_officiel():
    """R-H3 : exemple de la fiche 2681 (39 h, 10 HS aléatoires, deux semaines d'absence,
    rapport 1 230,73 / 2 285,65). Publié : 1 176,63 € au SMIC 2024. En 2026 :
    1 823,03 × r + (10 + 17,33 × r) × 12,02 = 1 213,99 €."""
    publie = smic_au_rapport_des_salaires(
        151.67, 1230.73, 2285.65, heures_structurelles=17.33, heures_sup_occasionnelles=10.0,
        smic_h=SMIC_H_2024)
    assert publie == 1176.63
    assert smic_au_rapport_des_salaires(
        151.67, 1230.73, 2285.65, heures_structurelles=17.33, heures_sup_occasionnelles=10.0,
    ) == 1213.99
    # Même fiche, exemple avec DFS (retenue sur l'horaire réel de 156 h) : publié 1 100,90 €.
    assert smic_au_rapport_des_salaires(
        151.67, 1142.82, 2285.65, heures_structurelles=17.33, heures_sup_occasionnelles=10.0,
        smic_h=SMIC_H_2024) == 1100.90


def test_r_h3_le_rapport_rejoint_la_soustraction_ou_le_prorata_selon_la_retenue():
    """R-H3 : 7 h d'absence sur un salaire de 2 000 €. Retenue valorisée sur 151,67 h : le
    rapport donne la soustraction (1 823,03 − 7 × 12,02 = 1 738,89). Retenue valorisée sur
    161 h réelles : le prorata de ces heures (1 823,03 × 154 / 161 = 1 743,77)."""
    retenue_151 = 7 * 2000.0 / 151.67
    assert smic_au_rapport_des_salaires(151.67, 2000.0 - retenue_151, 2000.0) == 1738.89
    retenue_161 = 7 * 2000.0 / 161
    assert smic_au_rapport_des_salaires(151.67, 2000.0 - retenue_161, 2000.0) == 1743.77


def test_r_h4_arret_avec_paiement_integral_smic_complet_heures_structurelles_comprises():
    """R-H4 (4e alinéa) : paiement intégral du brut, SMIC du mois complet, 17,33 h structurelles
    comprises : 1 823,03 + 17,33 × 12,02 = 2 031,34."""
    assert smic_mois_complet(151.67, 17.33, 0.0) == 2031.34


def test_r_h4_maintien_partiel_ijss_subrogees_hors_du_rapport():
    """R-H4 (5e alinéa) : exemples de la fiche 2681, IJSS déduites du brut.
    - carence de 7 jours puis 90 % : 1 391,10 / 2 285,65, publié 1 198,27 au SMIC 2024 ;
      en 2026 : 1 236,32 ;
    - prime d'ancienneté et maladie : 1 691,73 / 2 149,92, publié 1 390,35 ;
    - garantie sur le net : 1 104,27 / 1 820,04, publié 1 072,04."""
    assert smic_au_rapport_des_salaires(
        151.67, 1391.10, 2285.65, heures_structurelles=17.33, smic_h=SMIC_H_2024) == 1198.27
    assert smic_au_rapport_des_salaires(151.67, 1391.10, 2285.65, heures_structurelles=17.33) == 1236.32
    assert smic_au_rapport_des_salaires(151.67, 1691.73, 2149.92, smic_h=SMIC_H_2024) == 1390.35
    assert smic_au_rapport_des_salaires(151.67, 1104.27, 1820.04, smic_h=SMIC_H_2024) == 1072.04


def test_r_h4_aucun_maintien_sur_tout_le_mois_smic_nul():
    """R-H4 et R-A2 (b) : aucun maintien sur un mois entier, rapport nul, SMIC du mois = 0."""
    assert rapport_des_salaires(0.0, 2000.0) == 0.0
    assert smic_au_rapport_des_salaires(151.67, 0.0, 2000.0, heures_structurelles=17.33) == 0.0


def test_point_non_tranche_1_maintien_a_100_pour_cent_subroge_deux_variantes():
    """R-H4, R-H5, point non tranché n° 1 : maintien à 100 % sous déduction des IJSS.
    Brut soumis 2 285,65 − 262,99 d'IJSS = 2 022,66. « smic_entier » (lecture de Quadra) :
    2 031,34. « rapport_salaires » : 2 031,34 × 2 022,66 / 2 285,65 = 1 797,61."""
    commun = {"heures_structurelles": 17.33}
    assert smic_maintien_subroge(151.67, 2022.66, 2285.65, variante="smic_entier", **commun) == 2031.34
    assert smic_maintien_subroge(151.67, 2022.66, 2285.65, variante="rapport_salaires", **commun) == 1797.61
    with pytest.raises(TypeError):
        smic_maintien_subroge(151.67, 2022.66, 2285.65, **commun)   # pas de variante par défaut
    with pytest.raises(ValueError):
        smic_maintien_subroge(151.67, 2022.66, 2285.65, variante="soustraction", **commun)


def test_point_non_tranche_1_au_forfait_jours_deux_variantes():
    """R-H9 et point non tranché n° 1 : un salarié au forfait de 216 jours, en arrêt subrogé
    maintenu à 100 %, passe aussi par la variante. Brut soumis 2 700 sur 3 000 :
    « smic_entier » 1 806,30 ; « rapport_salaires » 1 806,30… × 0,9 = 1 625,67."""
    assert smic_maintien_subroge(None, 2700.0, 3000.0, variante="smic_entier",
                                 jours_forfait=216) == FORFAIT_216
    assert smic_maintien_subroge(None, 2700.0, 3000.0, variante="rapport_salaires",
                                 jours_forfait=216) == 1625.67
    with pytest.raises(TypeError):
        smic_maintien_subroge(None, 2700.0, 3000.0, jours_forfait=216)


def test_r_h5_absence_payee_par_l_employeur_rapport_egal_a_1():
    """R-H5 : événement familial payé, salaire inchangé : rapport 1, SMIC complet. Sans
    maintien : les jours du congé réduisent le SMIC du rapport des salaires."""
    assert smic_au_rapport_des_salaires(151.67, 2000.0, 2000.0, heures_structurelles=17.33) == 2031.34
    assert smic_au_rapport_des_salaires(151.67, 1500.0, 2000.0) == 1367.27   # 1 823,03 × 0,75


def test_r_h6_ferie_chome_non_paye_au_rapport_ferie_paye_smic_complet():
    """R-H6 : férié chômé non payé (moins de 3 mois d'ancienneté), 7 h retenues sur 151,67 h :
    rapport des salaires, 1 738,89 ; férié payé ou solidarité travaillée sans paie : salaire
    inchangé, SMIC complet, aucune heure ajoutée."""
    assert smic_au_rapport_des_salaires(151.67, 2000.0 - 7 * 2000.0 / 151.67, 2000.0) == 1738.89
    assert smic_au_rapport_des_salaires(151.67, 2000.0, 2000.0) == SMIC_DU_MOIS_2026


def test_r_h7_entree_le_1er_ou_sortie_le_dernier_jour_smic_entier():
    """R-H7 : arrivée le 1er ou départ le dernier jour du mois : le mois n'est pas incomplet,
    SMIC entier. Tout autre jour : mois incomplet."""
    assert mois_incomplet(2026, 3, date_entree=date(2026, 3, 1)) is False
    assert mois_incomplet(2026, 2, date_sortie=date(2026, 2, 28)) is False   # 2026 non bissextile
    assert mois_incomplet(2026, 5, date_entree=date(2025, 9, 1), date_sortie=date(2026, 5, 31)) is False
    assert mois_incomplet(2026, 3, date_entree=date(2026, 3, 2)) is True
    assert mois_incomplet(2026, 1, date_sortie=date(2026, 1, 30)) is True


def test_r_h7_mois_d_entree_au_rapport_des_salaires_et_non_des_heures():
    """R-H7 : entrée le 16, paie proratisée sur 12 jours ouvrés de 22 : 2 000 × 12 / 22 =
    1 090,91 €. SMIC = 1 823,03 × 1 090,91 / 2 000 = 994,38 (le calcul en heures du brief,
    84 h / 151,67, aurait donné 1 009,66)."""
    assert smic_entree_sortie(151.67, 1090.91, 2000.0) == 994.38


def test_r_h7_temps_partiel_double_prorata():
    """R-H7 et R-H8 : temps partiel à 121,33 h sorti à mi-mois : 12,02 × 121,33 × 0,5 = 729,19."""
    assert smic_entree_sortie(121.33, 800.0, 1600.0) == 729.19


def test_r_h7_sortie_au_forfait_jours_garde_la_variante_de_preavis():
    """R-H7, R-H9, point non tranché n° 4 : sortie à mi-mois d'un salarié au forfait de 216
    jours, 1 500 dus sur 3 000, 3 000 d'indemnité de préavis. « hors_rapport » : 1 806,30… ×
    0,5 = 903,15 ; « dans_rapport » : 1 806,30."""
    assert smic_entree_sortie(None, 1500.0, 3000.0, jours_forfait=216, indemnite_preavis=3000.0,
                              variante_preavis="hors_rapport") == 903.15
    assert smic_entree_sortie(None, 1500.0, 3000.0, jours_forfait=216, indemnite_preavis=3000.0,
                              variante_preavis="dans_rapport") == FORFAIT_216
    with pytest.raises(ValueError):
        smic_entree_sortie(None, 1500.0, 3000.0, jours_forfait=216, indemnite_preavis=3000.0)


def test_r_h7_mois_apres_la_rupture_aucun_smic():
    """R-H7 et R-A2 (d) : sommes rattachées à un mois sans jour de contrat : aucun SMIC."""
    with pytest.raises(ValueError):
        mois_incomplet(2026, 4, date_sortie=date(2026, 3, 31))
    with pytest.raises(ValueError):
        mois_incomplet(2026, 4, date_entree=date(2026, 5, 4))


def test_point_non_tranche_4_indemnite_de_preavis_deux_variantes():
    """R-H7, point non tranché n° 4 : sortie à mi-mois, 1 000 € dus hors indemnités de rupture
    sur 2 000 €, 2 000 € d'indemnité compensatrice de préavis. « hors_rapport » : 911,52 ;
    « dans_rapport » : rapport plafonné à 1, 1 823,03. Pas de choix implicite, et une variante
    inconnue est refusée même sans indemnité."""
    assert smic_entree_sortie(151.67, 1000.0, 2000.0, indemnite_preavis=2000.0,
                              variante_preavis="hors_rapport") == 911.52
    assert smic_entree_sortie(151.67, 1000.0, 2000.0, indemnite_preavis=2000.0,
                              variante_preavis="dans_rapport") == SMIC_DU_MOIS_2026
    with pytest.raises(ValueError):
        smic_entree_sortie(151.67, 1000.0, 2000.0, indemnite_preavis=2000.0)
    with pytest.raises(ValueError):
        smic_entree_sortie(151.67, 1000.0, 2000.0, variante_preavis="retiree")
    assert smic_entree_sortie(151.67, 1000.0, 2000.0) == 911.52   # sans préavis, rien à trancher


def test_r_h8_temps_partiel_12_02_fois_heures_du_contrat_plus_complementaires():
    """R-H8 : 12,02 × 121,33 = 1 458,39 ; avec 4 h complémentaires : 12,02 × 125,33 = 1 506,47."""
    assert smic_mois_complet(121.33, 0.0, 0.0) == 1458.39
    assert smic_mois_complet(121.33, 0.0, 4.0) == 1506.47


def test_r_h8_temps_partiel_de_la_fiche_2681_divergence_connue_d_un_centime():
    """R-H8 : exemple « temps partiel, IJSS et paniers » de la fiche 2681 (86,67 h, rapport
    735,07 / 1 205,15, SMIC 2024). La fiche proratise le SMIC mensuel arrondi :
    1 766,92 × 86,67 / 151,67 = 1 009,69, arrondi, puis × r = 615,85. R-H8 impose 12,02 ×
    heures du contrat (ici 11,65 × 86,67 = 1 009,7055, non arrondi), puis × r = 615,86.
    Divergence connue d'un centime, due à la formule de R-H8 et non à une erreur."""
    assert smic_au_rapport_des_salaires(86.67, 735.07, 1205.15, smic_h=SMIC_H_2024) == 615.86


def test_heures_complementaires_ajoutees_hors_du_rapport():
    """R-H8 et choix de calcul n° 3 : sous un rapport, les heures complémentaires s'ajoutent
    entières, hors du « × r », comme les heures supplémentaires occasionnelles.
    - temps partiel 121,33 h, rapport 0,5, 4 h complémentaires :
      12,02 × 121,33 × 0,5 + 4 × 12,02 = 777,27 (entrée ou sortie comme absence) ;
    - 39 h en maintien subrogé, rapport 0,9, 4 h complémentaires :
      (1 823,03 + 17,33 × 12,02) × 0,9 + 4 × 12,02 = 1 876,28 ; « smic_entier » : 2 079,42."""
    assert smic_au_rapport_des_salaires(121.33, 800.0, 1600.0, heures_comp=4.0) == 777.27
    assert smic_entree_sortie(121.33, 800.0, 1600.0, heures_comp=4.0) == 777.27
    commun = {"heures_structurelles": 17.33, "heures_comp": 4.0}
    assert smic_maintien_subroge(151.67, 1800.0, 2000.0, variante="rapport_salaires", **commun) == 1876.28
    assert smic_maintien_subroge(151.67, 1800.0, 2000.0, variante="smic_entier", **commun) == 2079.42


def test_r_h9_forfait_216_jours_mois_complet():
    """R-H9 : 1 823,03 × 216 / 218 = 1 806,30 (valeur retenue) ; 218 jours et au-delà :
    SMIC entier, jamais majoré pour des jours de repos rachetés. La fonction ne sert qu'au
    mois complet : plus de `rapport` par défaut qui choisirait en silence."""
    assert smic_forfait_jours(216) == FORFAIT_216
    assert smic_forfait_jours(218) == SMIC_DU_MOIS_2026
    assert smic_forfait_jours(230) == SMIC_DU_MOIS_2026
    with pytest.raises(TypeError):
        smic_forfait_jours(216, rapport=0.5)


def test_r_h9_absence_au_forfait_au_rapport_des_salaires():
    """R-H9 et point non tranché n° 8 : 2 jours d'absence sur 3 000 €, retenue sur 21,67 jours :
    1 806,30… × 2 723,12 / 3 000 = 1 639,59, et non « jours d'absence ÷ (216 / 12) ».
    Durée et forfait s'excluent ; un forfait jours n'a pas d'heures supplémentaires."""
    due = 3000.0 - 2 * 3000.0 / 21.67
    assert smic_au_rapport_des_salaires(None, due, 3000.0, jours_forfait=216) == 1639.59
    with pytest.raises(ValueError):
        smic_au_rapport_des_salaires(151.67, due, 3000.0, jours_forfait=216)
    with pytest.raises(ValueError):
        smic_au_rapport_des_salaires(None, due, 3000.0)
    with pytest.raises(ValueError):
        smic_au_rapport_des_salaires(None, due, 3000.0, jours_forfait=216, heures_sup_occasionnelles=5.0)


def test_r_h10_apprenti_paye_sous_le_smic_compte_pour_un_smic_entier():
    """R-H10 : apprenti payé 53 % du SMIC (966,21 €), présent tout le mois : le rapport porte
    sur son propre salaire (966,21 / 966,21), pas sur le SMIC (966,21 / 1 823,03 = 0,53) :
    SMIC de référence entier, 1 823,03. Absent la moitié du mois : 911,52."""
    assert smic_au_rapport_des_salaires(151.67, 966.21, 966.21) == SMIC_DU_MOIS_2026
    assert smic_au_rapport_des_salaires(151.67, 483.11, 966.21) == 911.52


def test_r_h11_activite_partielle_indemnite_hors_du_rapport():
    """R-H11 : 35 h chômées retenues sur 151,67 h, indemnité d'activité partielle hors brut :
    1 823,03 × 1 538,47 / 2 000 = 1 402,34."""
    assert smic_au_rapport_des_salaires(151.67, 2000.0 - 35 * 2000.0 / 151.67, 2000.0) == 1402.34


def test_r_h12_elements_sans_heures_n_ajoutent_pas_de_smic():
    """R-H12 : une prime entre au brut sans ajouter de SMIC ; non affectée par l'absence, elle
    sort des deux termes du rapport. Exemples de la fiche 2681 (SMIC 2024) : prime annuelle,
    1 000 / 2 000 → 883,46 ; prime d'ancienneté maintenue, 1 850 / 2 000 → 1 634,40 ;
    proratisée, 2 050 / 2 266,67 → 1 598,02."""
    assert smic_au_rapport_des_salaires(151.67, 1000.0, 2000.0, smic_h=SMIC_H_2024) == 883.46
    assert smic_au_rapport_des_salaires(151.67, 1850.0, 2000.0, smic_h=SMIC_H_2024) == 1634.40
    assert smic_au_rapport_des_salaires(151.67, 2050.0, 2266.67, smic_h=SMIC_H_2024) == 1598.02


def test_choix_2_arrondi_au_centime_demi_au_superieur():
    """Choix de calcul n° 2 : 1 823,03 × 0,5 = 911,515 → 911,52 (demi au supérieur), là où
    round() de Python donne 911,51 ; 1 823,03 + 0,75 × 12,02 = 1 832,045 → 1 832,05, là où
    l'arrondi au pair donnerait 1 832,04."""
    assert round(1823.03 * 0.5, 2) == 911.51
    assert smic_au_rapport_des_salaires(151.67, 1000.0, 2000.0) == 911.52
    assert smic_mois_complet(151.67, 0.75, 0.0) == 1832.05


def test_choix_3_rapport_plafonne_a_1_heures_occasionnelles_hors_plafond():
    """Choix de calcul n° 3 : rapport = min(1, numérateur / dénominateur) ; les heures
    supplémentaires occasionnelles s'ajoutent ensuite : 1 823,03 + 10 × 12,02 = 1 943,23."""
    assert rapport_des_salaires(2500.0, 2000.0) == 1.0
    assert smic_au_rapport_des_salaires(151.67, 2500.0, 2000.0, heures_sup_occasionnelles=10.0) == 1943.23
