"""Le planning postérieur à la sortie n'est ni payé ni compté, et le bulletin le dit.

Retour de la réunion du 10/11/2026 (Colorplast, F.A.O.) : fin de CDD le 02/10,
planning pré-rempli de travail jusqu'à la fin d'octobre (et un arrêt maladie
les 08 et 09/10).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.planning_apres_sortie import (
    CODE_ALERTE_PLANNING_APRES_SORTIE,
    alerte_planning_apres_sortie,
    date_de_sortie,
    ecarter_apres_la_sortie,
)

pytestmark = pytest.mark.unit


def _jour(j: int, type_: str, heures: float | None = None, cle: str = "heures_prevues") -> dict:
    return {"annee": 2026, "mois": 10, "jour": j, "type": type_, cle: heures}


PREVU = [
    _jour(1, "travail", 8.5),
    _jour(2, "travail", 5.0),
    _jour(3, "repos", 0.0),
    _jour(5, "travail", 8.5),
    _jour(8, "arret_maladie", 0.0),
    _jour(10, "repos", 0.0),
]
REEL = [
    _jour(1, "travail", 9.0, "heures_faites"),
    _jour(2, "travail", 5.0, "heures_faites"),
    _jour(5, "travail", 0.0, "heures_faites"),
    _jour(6, "travail", 7.0, "heures_faites"),
]


class TestEcarter:
    def test_les_jours_apres_la_sortie_disparaissent(self):
        prevu, reel, ecartes = ecarter_apres_la_sortie(PREVU, REEL, date(2026, 10, 2))
        assert [j["jour"] for j in prevu] == [1, 2]
        assert [j["jour"] for j in reel] == [1, 2]
        # Le repos ne porte rien ; le réel du 05 à 0 h non plus, mais son prévu oui.
        assert ecartes == [date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 8)]

    def test_sans_sortie_rien_ne_change(self):
        prevu, reel, ecartes = ecarter_apres_la_sortie(PREVU, REEL, None)
        assert len(prevu) == len(PREVU) and len(reel) == len(REEL)
        assert ecartes == []

    def test_le_jour_de_la_sortie_reste(self):
        prevu, _, _ = ecarter_apres_la_sortie(PREVU, REEL, date(2026, 10, 5))
        assert [j["jour"] for j in prevu] == [1, 2, 3, 5]

    def test_date_texte(self):
        assert date_de_sortie("2026-10-02") == date(2026, 10, 2)
        assert date_de_sortie(None) is None
        assert date_de_sortie("n/a") is None


class TestAlerte:
    def test_alerte_nomme_les_jours_du_mois(self):
        alerte = alerte_planning_apres_sortie(
            [date(2026, 10, 5), date(2026, 10, 30), date(2026, 11, 2)],
            date(2026, 10, 2),
            2026,
            10,
        )
        assert alerte["code"] == CODE_ALERTE_PLANNING_APRES_SORTIE
        assert alerte["critique"] is False
        assert "02/10/2026" in alerte["message"]
        assert "2 jours" in alerte["message"]
        assert "du 05/10 au 30/10" in alerte["message"]

    def test_fenetre_qui_deborde(self):
        alerte = alerte_planning_apres_sortie(
            [date(2026, 11, 2)], date(2026, 10, 30), 2026, 10, fin_fenetre=date(2026, 11, 5)
        )
        assert alerte is not None and "le 02/11" in alerte["message"]

    def test_rien_dans_la_periode(self):
        assert (
            alerte_planning_apres_sortie([date(2026, 12, 1)], date(2026, 10, 2), 2026, 10)
            is None
        )
        assert alerte_planning_apres_sortie([date(2026, 10, 5)], None, 2026, 10) is None
