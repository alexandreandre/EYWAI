"""Absences fictives évitées quand un mois sans pointage est replié sur le planning."""

from __future__ import annotations

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.planning_repli import (
    appliquer_repli_sans_pointage_par_mois,
    mois_sans_pointage,
    reel_heures_avec_repli_planning_si_sans_pointage,
)


def _prevu(mois: int, jour: int, heures: float, *, annee: int = 2026) -> dict:
    return {
        "annee": annee,
        "mois": mois,
        "jour": jour,
        "type": "travail",
        "heures_prevues": heures,
    }


class TestAnalyzerSansPointageRepli:
    def test_repli_injecte_heures_planning_avril(self):
        prevu = [_prevu(4, d, 8.0) for d in (20, 21, 22, 23, 24)]
        reel: list[dict] = []
        assert mois_sans_pointage(reel, annee=2026, mois=4) is True

        out = reel_heures_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=4
        )
        assert len(out) == 5
        assert all(j.get("heures_faites") == 8.0 for j in out)

    def test_analyse_mai_sans_absence_avril_apres_repli(self):
        """Portion avril de la période mai : planning repris, pas de retenue."""
        prevu = [_prevu(4, d, 8.0) for d in (20, 21, 22)] + [
            _prevu(5, d, 8.0) for d in (5, 6, 7)
        ]
        reel_mai = [
            {
                "annee": 2026,
                "mois": 5,
                "jour": 5,
                "type": "travail",
                "heures_faites": 8.0,
            }
        ]
        actual = appliquer_repli_sans_pointage_par_mois(
            prevu, reel_mai, [(2026, 4), (2026, 5)], is_forfait_jour=False
        )
        events_avril = analyser_horaires_du_mois(
            prevu, actual, 35.0, 2026, 4, "test"
        )
        assert not any("absence_injustifiee" in e.get("type", "") for e in events_avril)

    def test_pointage_partiel_inchange(self):
        prevu = [_prevu(4, 21, 8.0)]
        reel = [
            {"annee": 2026, "mois": 4, "jour": 21, "type": "travail", "heures_faites": 7.0}
        ]
        out = reel_heures_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=4
        )
        assert out == reel
