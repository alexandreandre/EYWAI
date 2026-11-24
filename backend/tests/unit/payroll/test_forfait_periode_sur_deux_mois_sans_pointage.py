"""Forfait jours, période de paie à cheval sur deux mois, sans pointage (24/11).

Le repli « sans pointage, on paie le planning » ne couvrait que le mois du
bulletin. Les jours du mois d'avant compris dans la période (du 23 au 31 octobre
pour une période close le 19 novembre) restaient sans réel : avec un prévu à 1,
chacun devenait une absence injustifiée retenue (bac à sable du 24/11 : un cadre
de Cartol passait de 4 457,85 € à 3 420,44 € de net). Le générateur des heures
appliquait déjà le repli à chaque mois (`appliquer_repli_sans_pointage_par_mois`) ;
le forfait fait de même.
"""
from __future__ import annotations

import calendar
from datetime import date

import pytest

from app.modules.payroll.engine.analyser_jours_forfait import analyser_jours_forfait_du_mois

pytestmark = pytest.mark.unit


def _prevu(annee: int, mois: int, valeur: float) -> list[dict]:
    jours = []
    for j in range(1, calendar.monthrange(annee, mois)[1] + 1):
        ouvre = date(annee, mois, j).isoweekday() <= 5
        jours.append({
            "annee": annee, "mois": mois, "jour": j,
            "type": "travail" if ouvre else "weekend",
            "heures_prevues": valeur if ouvre else 0,
        })
    return jours


def _evenements(valeur: float, reel: list[dict] | None = None) -> list[dict]:
    prevu = _prevu(2026, 10, valeur) + _prevu(2026, 11, valeur) + _prevu(2026, 12, valeur)
    return analyser_jours_forfait_du_mois(
        prevu, reel or [], 2026, 11, "test",
        date_debut_periode=date(2026, 10, 23), date_fin_periode=date(2026, 11, 19),
    )


@pytest.mark.parametrize("valeur", [1, 7.0])
def test_sans_pointage_aucune_absence_sur_les_jours_du_mois_d_avant(valeur):
    absences = [e for e in _evenements(valeur) if "absence" in e["type"]]
    assert absences == []


def test_sans_pointage_tous_les_jours_ouvres_de_la_periode_sont_travailles():
    travailles = {
        (e["mois"], e["jour"]) for e in _evenements(1) if e["type"] == "travail_base"
    }
    # 23-30 octobre (6 jours ouvrés) et 2-19 novembre (14 jours ouvrés).
    assert len(travailles) == 20
    assert (10, 23) in travailles and (11, 19) in travailles


def test_un_zero_pose_le_mois_d_avant_reste_une_absence():
    """Octobre pointé en partie : un 0 posé dit « non travaillé », le reste est complété.

    (Un mois sans aucun jour > 0 est un mois « sans pointage » : le repli le
    remplace entier, 0 compris, comme pour le mois du bulletin.)"""
    reel = [
        {"annee": 2026, "mois": 10, "jour": 23, "type": "reel", "heures_faites": 1},
        {"annee": 2026, "mois": 10, "jour": 26, "type": "reel", "heures_faites": 0},
    ]
    absences = {(e["mois"], e["jour"]) for e in _evenements(1, reel) if "absence" in e["type"]}
    assert absences == {(10, 26)}


def test_un_reel_reste_en_heures_compte_pour_un_jour_travaille():
    """Un réel écrit en heures (import d'avant le 24/11) face à un prévu à 1 :
    le salarié a travaillé, ce n'est jamais une absence injustifiée."""
    reel = [
        {"annee": 2026, "mois": 11, "jour": j, "type": "travail", "heures_faites": 7.0}
        for j in range(2, 20) if date(2026, 11, j).isoweekday() <= 5
    ] + [
        {"annee": 2026, "mois": 10, "jour": j, "type": "travail", "heures_faites": 7.0}
        for j in range(23, 32) if date(2026, 10, j).isoweekday() <= 5
    ]
    evenements = _evenements(1, reel)
    assert [e for e in evenements if "absence" in e["type"]] == []
    assert len({(e["mois"], e["jour"]) for e in evenements if e["type"] == "travail_base"}) == 20
