"""Arrêts de l'année repris des bulletins Quadra : lus, recollés, typés."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, Ligne
from scripts.reprise_arrets_quadra import arrets_des_bulletins, recoller

pytestmark = pytest.mark.unit


def _bulletin(*libelles) -> Bulletin:
    b = Bulletin(matricule="ESSAI")
    b.lignes = [Ligne(None, lib, base=7.0) for lib in libelles]
    return b


def test_les_lignes_d_arret_sont_lues_et_typees():
    b = _bulletin("Absence maladie 040526-310526", "Absence A.T. 050526-140526",
                  "Abs. paternité 190226-280226", "Abs. Congés s.so 050526-060526",
                  "Congés payés : 030826-140826")
    assert arrets_des_bulletins({5: {"ESSAI": b}})["ESSAI"] == [
        ("arret_paternite", None, date(2026, 2, 19), date(2026, 2, 28)),
        ("arret_maladie", "maladie_simple", date(2026, 5, 4), date(2026, 5, 31)),
        ("arret_at", "accident_travail", date(2026, 5, 5), date(2026, 5, 14)),
    ]


def test_un_arret_decoupe_par_mois_est_recolle():
    """Quadra coupe à la fin de chaque période ; un week-end entre deux morceaux
    (30/05 puis 01/06) ne coupe pas l'arrêt, une reprise d'une semaine si."""
    morceaux = [
        ("arret_maladie", "maladie_simple", date(2026, 4, 27), date(2026, 4, 30)),
        ("arret_maladie", "maladie_simple", date(2026, 5, 1), date(2026, 5, 30)),
        ("arret_maladie", "maladie_simple", date(2026, 6, 1), date(2026, 6, 26)),
        ("arret_maladie", "maladie_simple", date(2026, 7, 20), date(2026, 7, 31)),
    ]
    assert recoller(morceaux) == [
        ("arret_maladie", "maladie_simple", date(2026, 4, 27), date(2026, 6, 26)),
        ("arret_maladie", "maladie_simple", date(2026, 7, 20), date(2026, 7, 31)),
    ]


def test_deux_natures_differentes_ne_se_recollent_pas():
    morceaux = [
        ("arret_maladie", "maladie_simple", date(2026, 5, 1), date(2026, 5, 10)),
        ("arret_at", "accident_travail", date(2026, 5, 11), date(2026, 5, 20)),
    ]
    assert recoller(morceaux) == morceaux
