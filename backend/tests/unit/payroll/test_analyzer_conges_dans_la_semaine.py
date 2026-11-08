"""Heure faite en plus une semaine de congés ou d'arrêt (R-260).

Cass. soc. 10/09/2025 n° 23-14.455, § 18 : en décompte hebdomadaire, le salarié
« peut prétendre au paiement des majorations pour heures supplémentaires qu'il
aurait perçues s'il avait travaillé durant toute la semaine » quand il a été
partiellement en congé payé. L'arrêt ne vise pas la maladie.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois

pytestmark = pytest.mark.unit


def _semaine(types_lundi_mardi: tuple[str, float]):
    """Lundi 05/10/2026 et mardi d'absence, mercredi à vendredi pointés à 7, 7 et 8 h."""
    type_absence, heures_absence = types_lundi_mardi
    prevu = [
        {"annee": 2026, "mois": 10, "jour": j, "type": type_absence, "heures_prevues": heures_absence}
        for j in (5, 6)
    ] + [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_prevues": 7.0}
        for j in (7, 8, 9)
    ]
    reel = [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_faites": h}
        for j, h in ((7, 7.0), (8, 7.0), (9, 8.0))
    ]
    return prevu, reel


def _hs25(evenements) -> float:
    return round(sum(e["heures"] for e in evenements if e["type"] == "travail_hs25"), 2)


def test_un_conge_pose_a_l_ecran_compte_pour_sa_journee():
    prevu, reel = _semaine(("conges_payes", 0))
    assert _hs25(analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 10, "T")) == 1.0


def test_un_conge_du_planning_garde_ses_heures_prevues():
    prevu, reel = _semaine(("conges_payes", 7.0))
    assert _hs25(analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 10, "T")) == 1.0


def test_une_semaine_d_arret_maladie_ne_majore_pas():
    prevu, reel = _semaine(("arret_maladie", 0))
    assert _hs25(analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 10, "T")) == 0.0
