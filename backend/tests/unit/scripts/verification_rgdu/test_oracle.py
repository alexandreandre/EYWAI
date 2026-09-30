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
