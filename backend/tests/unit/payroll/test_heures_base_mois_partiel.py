"""Compteur d'heures d'un mois d'entrée : les heures dues, pas le mois plein.

Demory est embauché le 23/03/2026 chez Colorplast. Son bulletin Quadra porte
47,50 h de base et 3,00 h structurelles, soit 50,50 h de période. Nous
comptions 154,67 h — les 151,67 h d'un mois plein plus ses 3 h — parce que le
compteur partait de la durée contractuelle mensuelle sans regarder ce qui avait
réellement été payé.

Le compteur alimente le SMIC de référence de la réduction générale : un mois
d'entrée comptant trois fois trop d'heures donne un allègement très surévalué
(−248,91 au lieu des −201,39 du cabinet).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _heures_comptees(resultat_brut: dict, heures_contractuelles: float,
                     heures_legales: float, heures_supp: float) -> float:
    """Le calcul du compteur, isolé de `payslip_run_heures`."""
    heures_base = float(
        resultat_brut.get("heures_base_remunerees")
        or min(heures_contractuelles, heures_legales)
    )
    return round(max(0.0, heures_base + heures_supp), 2)


def test_mois_d_entree_compte_les_heures_dues():
    """Demory, embauché le 23/03 : 47,50 h de base + 3,00 h structurelles."""
    assert _heures_comptees(
        {"heures_base_remunerees": 47.50}, 169.0, 151.67, 3.0
    ) == 50.50


def test_mois_plein_inchange():
    """Bugny en mars : 151,67 h de base + 43,33 h sup = 195,00 h."""
    assert _heures_comptees(
        {"heures_base_remunerees": 151.67}, 169.0, 151.67, 43.33
    ) == 195.00


def test_repli_quand_le_brut_ne_dit_rien():
    """Un résultat sans la clé retombe sur l'ancien calcul, au centième près."""
    assert _heures_comptees({}, 169.0, 151.67, 43.33) == 195.00
    assert _heures_comptees({"heures_base_remunerees": 0.0}, 169.0, 151.67, 0.0) == 151.67
