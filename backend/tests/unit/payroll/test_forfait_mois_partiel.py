"""Forfait jours : un jour prévu resté sans réel n'est pas une absence.

L'écran pose 1 (travaillé) ou 0 (non travaillé). Un mois confirmé en partie
changeait les jours restés « Prévu » en absences injustifiées, retenues sur le
salaire sans que personne ne les ait déclarées.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.analyser_jours_forfait import analyser_jours_forfait_du_mois
from app.modules.payroll.planning_repli import reel_heures_avec_repli_planning_si_sans_pointage

pytestmark = pytest.mark.unit

PREVU = [
    {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_prevues": 1}
    for j in (5, 6, 7, 8, 9)
]


def _reel(jour, heures):
    return {"annee": 2026, "mois": 10, "jour": jour, "type": "reel", "heures_faites": heures}


def _types(reel):
    return {
        e["jour"]: e["type"]
        for e in analyser_jours_forfait_du_mois(PREVU, reel, 2026, 10, "salarié")
    }


TOUS_TRAVAILLES = dict.fromkeys((5, 6, 7, 8, 9), "travail_base")


def test_mois_sans_aucun_reel_reste_travaille():
    assert _types([]) == TOUS_TRAVAILLES


def test_jours_sans_ligne_de_reel_restent_travailles():
    assert _types([_reel(5, 1), _reel(6, 1)]) == TOUS_TRAVAILLES


def test_jours_sans_valeur_restent_travailles():
    assert _types([_reel(5, 1), _reel(6, 1), _reel(7, None), _reel(8, None), _reel(9, None)]) == (
        TOUS_TRAVAILLES
    )


def test_un_zero_pose_a_l_ecran_reste_une_absence():
    types = _types([_reel(5, 1), _reel(6, 1), _reel(7, 0), _reel(8, 1), _reel(9, 1)])
    assert types[7] == "absence_injustifiee_base"
    assert [j for j, t in types.items() if t != "travail_base"] == [7]


def test_en_heures_un_mois_confirme_en_partie_ne_recoit_aucune_heure_inventee():
    """Filet du 06/11 : 1 h posée par jour manquant faisait chuter les nets de 27 bulletins."""
    prevu = [
        {"annee": 2026, "mois": 6, "jour": j, "type": "travail", "heures_prevues": 7.0}
        for j in (1, 2, 3)
    ]
    reel = [{"annee": 2026, "mois": 6, "jour": 1, "type": "travail", "heures_faites": 7.0}]

    assert reel_heures_avec_repli_planning_si_sans_pointage(prevu, reel, annee=2026, mois=6) == reel
