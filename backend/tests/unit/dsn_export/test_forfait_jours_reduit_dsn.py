"""Quotité DSN d'un forfait jours réduit (registre R-450).

Fiche net-entreprises n° 3369 (modifiée le 03/04/2026) : 100 jours pour une
référence de 21,67 → quotité du contrat 9,94, soit jours × 21,67 / 218, et
modalité « 10 - temps plein », car un forfait jours n'est pas un temps partiel
(Cass. soc., 12 mars 2014, n° 12-29.141). L'ancien logiciel trouve aussi 4,27
pour 43 jours, mais déclarait à tort la modalité 20.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.contract_map import map_modalite_temps

pytestmark = pytest.mark.unit


def _forfait(jours, reference="21.67", temps_partiel=False):
    return map_modalite_temps(
        is_forfait_jour=True,
        quotite_forfait_jours=reference,
        is_temps_partiel=temps_partiel,
        jours_forfait_salarie=jours,
    )


def test_exemple_de_la_fiche_net_entreprises():
    assert _forfait(100) == ("20", "21.67", "9.94", "10")


def test_forfait_de_43_jours():
    assert _forfait(43) == ("20", "21.67", "4.27", "10")


def test_la_case_temps_partiel_ne_change_pas_la_modalite_d_un_forfait():
    assert _forfait(43, temps_partiel=True)[3] == "10"


def test_le_coefficient_ne_depend_pas_de_la_reference_de_la_societe():
    assert _forfait(171, reference="21.27")[2] == "17.00"


def test_sans_forfait_sur_la_fiche_la_quotite_reste_celle_de_la_societe():
    assert _forfait(None) == ("20", "21.67", "21.67", "10")


def test_un_forfait_plein_ne_depasse_jamais_la_reference():
    assert _forfait(218, reference="21.27") == ("20", "21.27", "21.27", "10")


def test_un_salarie_a_l_heure_ne_change_pas():
    assert map_modalite_temps(is_temps_partiel=True, duree_hebdo=28.0) == ("10", "151.67", "121.33", "20")
