"""Formule RGDU 2026 écrite depuis les textes (R-F1), vérifiée sur une DSN réelle anonymisée."""
import pytest

from scripts.verification_rgdu.oracle import (
    Parametres, coefficient, reduction_cumulee, reduction_du_mois, smic_pour_reduction,
)

pytestmark = pytest.mark.unit
P = Parametres()


def test_au_smic_le_coefficient_vaut_tmax():
    assert coefficient(1823.03, 1823.03, P) == 0.3981


def test_a_trois_smic_et_au_dela_rien():
    assert coefficient(3 * 1823.03, 1823.03, P) == 0.0
    assert coefficient(6000.0, 1823.03, P) == 0.0


def test_une_dsn_quadra_de_janvier_est_retrouvee_au_centime():
    """Salarié A, Colorplast, janvier 2026 : assiette 3 023,40, SMIC retenu 2 277,75,
    réduction déclarée 483,87 (018) + 86,04 (106) = 569,91."""
    assert coefficient(3023.40, 2277.75, P) == 0.1885
    assert reduction_cumulee(3023.40, 2277.75, P) == 569.91


def test_la_reduction_du_mois_est_la_regularisation_de_l_annee():
    jan = reduction_cumulee(3000.0, 2300.0, P)
    fev = reduction_du_mois(3000.0, 2300.0, jan, 3100.0, 2250.0, P)
    assert round(jan + fev, 2) == reduction_cumulee(6100.0, 4550.0, P)


def test_le_smic_implicite_redonne_la_reduction():
    smic = smic_pour_reduction(3023.40, 569.91, P)
    assert abs(smic - 2277.75) < 0.5


def test_une_cible_au_dela_du_maximum_atteignable_leve_une_erreur():
    with pytest.raises(ValueError):
        smic_pour_reduction(1000.0, 900.0, P)


def test_une_cible_egale_au_maximum_ne_leve_pas_et_se_retrouve():
    brut = 1000.0
    maximum = round(brut * P.tmax, 2)
    smic = smic_pour_reduction(brut, maximum, P)
    assert abs(reduction_cumulee(brut, smic, P) - maximum) <= 0.01


def test_une_cible_nulle_ou_negative_leve_une_erreur():
    with pytest.raises(ValueError):
        smic_pour_reduction(1000.0, 0.0, P)
    with pytest.raises(ValueError):
        smic_pour_reduction(1000.0, -10.0, P)


def test_une_cible_qui_expose_l_arrondi_du_maximum_est_quand_meme_retrouvee():
    """Sur ce brut, le maximum non arrondi (1203,61554) et son arrondi au centime
    (1203,62, la cible demandée ici) diffèrent : une comparaison non arrondie dans
    la dichotomie ne rencontre jamais 1203,62 et dérive vers 2 × brut en silence."""
    brut = 3023.40
    cible = 1203.62
    smic = smic_pour_reduction(brut, cible, P)
    assert smic <= brut
    assert abs(reduction_cumulee(brut, smic, P) - cible) <= 0.01


def test_deux_cents_bruts_realistes_retrouvent_leur_cible_sans_deriver():
    """Le coefficient légal est arrondi à 4 décimales (D241-7, II) : la réduction
    n'évolue donc que par paliers d'une dizaine à quelques dizaines de centimes,
    jamais au centime près, sur un brut cumulé de plusieurs milliers d'euros. Une
    cible prise à une fraction arbitraire du maximum en euros (ex. 60 % de 398,10 =
    238,86) peut tomber entre deux paliers et n'être atteignable par aucun SMIC — ce
    n'est pas une dérive de la dichotomie, c'est la formule elle-même. La cible à 60 %
    est donc construite avec la formule (comme le serait une vraie réduction déclarée
    par Quadra), pas comme une fraction arbitraire du montant maximal."""
    for i in range(200):
        brut = round(1000.0 + 37.13 * i, 2)
        maximum = reduction_cumulee(brut, brut, P)
        cible_60 = reduction_cumulee(brut, round(0.6 * brut, 2), P)
        for cible in (maximum, cible_60):
            smic = smic_pour_reduction(brut, cible, P)
            assert smic <= brut, (brut, cible, smic)
            assert abs(reduction_cumulee(brut, smic, P) - cible) <= 0.01, (brut, cible, smic)
