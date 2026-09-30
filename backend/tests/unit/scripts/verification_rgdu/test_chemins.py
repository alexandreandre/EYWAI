"""Tdelta par société (R-F3) : moins de 50 salariés (0,3781) ou 50 et plus (0,3821)."""
import pytest

from scripts.verification_rgdu.chemins import parametres_de

pytestmark = pytest.mark.unit


def test_mont_blanc_est_a_cinquante_salaries_et_plus():
    assert parametres_de("mbc").tmax == 0.4021


def test_colorplast_est_sous_cinquante_salaries():
    assert parametres_de("colorplast").tmax == 0.3981


def test_comitech_est_sous_cinquante_salaries():
    assert parametres_de("comitech").tmax == 0.3981


def test_une_societe_inconnue_leve_key_error():
    with pytest.raises(KeyError):
        parametres_de("inconnue")
