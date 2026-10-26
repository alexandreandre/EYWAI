"""Rejeu à trois colonnes : SMIC de Quadra (DSN puis implicite), loi, MARTINE (cache)."""
import pytest

from scripts.verification_rgdu.implicite import SmicImplicite
from scripts.verification_rgdu.oracle import Parametres
from scripts.verification_rgdu.quadra_mois import MoisQuadra
from scripts.verification_rgdu.regle_du_mois import SmicLoi
from scripts.verification_rgdu.rejouer import (
    MoisRejoue,
    comparer_un_salarie,
    smic_eywai,
    smic_quadra_du_mois,
)

pytestmark = pytest.mark.unit
P = Parametres()


def test_la_dsn_passe_avant_l_implicite():
    implicite = {7: SmicImplicite(2031.0, 14000.0, 0.0, False, True, "")}
    assert smic_quadra_du_mois(3, {3: 2031.34}, implicite) == (2031.34, "dsn")
    assert smic_quadra_du_mois(7, {3: 2031.34}, implicite) == (2031.0, "implicite")


def test_un_implicite_non_calculable_ne_donne_pas_de_smic():
    implicite = {8: SmicImplicite(None, None, None, False, False, "cascade")}
    assert smic_quadra_du_mois(8, {}, implicite) == (None, "implicite")
    assert smic_quadra_du_mois(9, {}, {}) == (None, "absent")


def test_le_cache_martine_ne_donne_que_les_calculs_aboutis():
    cache = {"A|3": {"statut": "ok", "smic": 2031.38}, "A|4": {"statut": "erreur"}}
    assert smic_eywai(cache, "A", 3) == 2031.38
    assert smic_eywai(cache, "A", 4) is None and smic_eywai(cache, "A", 5) is None


def _mois(m, cumul_bruts, reduction):
    mq = MoisQuadra("colorplast", m, "ESSAI", "1999999999999", 2400.0, cumul_bruts, 0.0, 169.0, reduction)
    return mq


def test_le_smic_cumule_de_quadra_avance_mois_par_mois_et_juin_a_12_31_est_a_juger():
    mois = [MoisRejoue(_mois(5, 2400.0, 0.0), SmicLoi(2031.34, regle="R-H1")),
            MoisRejoue(_mois(6, 4800.0, 0.0), SmicLoi(2031.34, regle="R-H1"))]
    lignes = comparer_un_salarie("colorplast", "A", mois, {5: 2031.34, 6: 2080.35},
                                 {"A|6": {"statut": "ok", "smic": 2031.38}}, P)
    (mai, r_mai), (juin, _) = lignes
    assert mai.preclassement == "identique" and r_mai == "R-H1"
    assert juin.smic_cumule_prec == 2031.34
    assert juin.preclassement == "a_juger_quadra" and juin.impact_quadra > 0
    assert juin.smic_eywai == 2031.38
