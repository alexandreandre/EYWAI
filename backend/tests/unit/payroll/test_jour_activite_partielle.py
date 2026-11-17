"""Un jour « Activité partielle » du calendrier n'est jamais retenu en absence.

Il est payé par les deux lignes d'activité partielle (retenue des heures
chômées, indemnité) que le générateur tire du calendrier. Avant, le seul
moyen de poser un jour chômé au calendrier (« Travail » à 0 h ou « Absence non
rémunérée ») retenait la journée une seconde fois.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.engine.analyser_jours_forfait import analyser_jours_forfait_du_mois

pytestmark = pytest.mark.unit


def _prevu(type_lundi, h=7.0):
    return [
        {"annee": 2026, "mois": 10, "jour": j, "type": type_lundi if j == 12 else "travail", "heures_prevues": h}
        for j in range(12, 17)
    ]


def _reel(lundi, h=7.0):
    reel = [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_faites": h}
        for j in range(13, 17)
    ]
    if lundi is not None:
        reel.append({"annee": 2026, "mois": 10, "jour": 12, "type": "travail", "heures_faites": lundi})
    return reel


def test_jour_chome_aucun_evenement():
    ev = analyser_horaires_du_mois(_prevu("activite_partielle"), _reel(None), 35.0, 2026, 10, "t")
    assert [e for e in ev if e["jour"] == 12] == []


def test_demi_journee_travaillee_sans_absence():
    ev = analyser_horaires_du_mois(_prevu("activite_partielle"), _reel(3.0), 35.0, 2026, 10, "t")
    assert not [e for e in ev if "absence" in e["type"]]


def test_forfait_jour_chome_aucun_evenement():
    ev = analyser_jours_forfait_du_mois(_prevu("activite_partielle", 1), _reel(None, 1), 2026, 10, "t")
    assert [e for e in ev if e["jour"] == 12] == []
