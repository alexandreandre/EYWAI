"""Un jour « travail » au réel sans heures est un jour non saisi, pas une absence.

Colorplast, 26 au 30/10/2026 : des jours marqués « travail » au calendrier réel,
sans heures, étaient retenus en absence injustifiée (une journée entière),
alors qu'un jour sans ligne au réel est payé au prévu et que l'écran du
calendrier promet « payés à plein » pour les deux. Seul un 0 saisi dit
« pas travaillé ».
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois

pytestmark = pytest.mark.unit

# Semaine 42 de 2026 : lundi 12 → vendredi 16 octobre, 7 h par jour.
JOURS = range(12, 17)


def _prevu():
    return [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_prevues": 7.0}
        for j in JOURS
    ]


def _reel(lundi):
    reel = [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_faites": 7.0}
        for j in JOURS
        if j != 12
    ]
    if lundi is not ...:
        reel.append({"annee": 2026, "mois": 10, "jour": 12, "type": "travail", **lundi})
    return reel


def _absences(ev):
    return [e for e in ev if str(e.get("type", "")).startswith("absence_injustifiee")]


def test_jour_travail_sans_heures_n_est_pas_retenu():
    ev = analyser_horaires_du_mois(_prevu(), _reel({"heures_faites": None}), 35.0, 2026, 10, "A.B.")
    assert _absences(ev) == []


def test_jour_travail_sans_cle_heures_n_est_pas_retenu():
    ev = analyser_horaires_du_mois(_prevu(), _reel({}), 35.0, 2026, 10, "A.B.")
    assert _absences(ev) == []


def test_meme_resultat_qu_un_jour_sans_ligne():
    sans_ligne = analyser_horaires_du_mois(_prevu(), _reel(...), 35.0, 2026, 10, "A.B.")
    sans_heures = analyser_horaires_du_mois(_prevu(), _reel({"heures_faites": None}), 35.0, 2026, 10, "A.B.")
    assert sans_heures == sans_ligne


def test_un_zero_saisi_reste_une_absence():
    ev = analyser_horaires_du_mois(_prevu(), _reel({"heures_faites": 0}), 35.0, 2026, 10, "A.B.")
    assert round(sum(e["heures"] for e in _absences(ev)), 2) == 7.0
