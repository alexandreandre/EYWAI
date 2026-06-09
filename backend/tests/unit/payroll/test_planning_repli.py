"""Tests unitaires du repli planning forfait sans pointage."""

from __future__ import annotations

from app.modules.payroll.planning_repli import (
    mois_sans_pointage,
    reel_forfait_avec_repli_planning_si_sans_pointage,
)


def _jour(mois: int, jour: int, heures: float, *, annee: int = 2026) -> dict:
    return {"annee": annee, "mois": mois, "jour": jour, "heures_faites": heures}


def _prevu(mois: int, jour: int, *, annee: int = 2026) -> dict:
    return {
        "annee": annee,
        "mois": mois,
        "jour": jour,
        "type": "travail",
        "heures_prevues": 1,
    }


class TestMoisSansPointage:
    def test_vide(self):
        assert mois_sans_pointage([], annee=2026, mois=6) is True

    def test_heures_nulles(self):
        reel = [_jour(6, 3, 0), _jour(6, 4, 0)]
        assert mois_sans_pointage(reel, annee=2026, mois=6) is True

    def test_avec_pointage(self):
        reel = [_jour(6, 3, 1)]
        assert mois_sans_pointage(reel, annee=2026, mois=6) is False

    def test_ignore_autre_mois(self):
        reel = [_jour(5, 3, 8)]
        assert mois_sans_pointage(reel, annee=2026, mois=6) is True


class TestRepliPlanningForfait:
    def test_sans_pointage_reprend_planning(self):
        prevu = [_prevu(6, 2), _prevu(6, 3), _prevu(6, 10)]
        reel = [_jour(5, 1, 1)]
        out = reel_forfait_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=6
        )
        jours_juin = [j for j in out if j.get("mois") == 6]
        assert len(jours_juin) == 3
        assert all(j.get("heures_faites") == 1 for j in jours_juin)
        assert all(j.get("type") == "reel" for j in jours_juin)

    def test_avec_pointage_inchange(self):
        prevu = [_prevu(6, 2)]
        reel = [_jour(6, 2, 1), _jour(5, 1, 1)]
        out = reel_forfait_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=6
        )
        assert out == reel

    def test_sans_planning_inchange(self):
        prevu = [_prevu(5, 2)]
        reel = [_jour(5, 1, 1)]
        out = reel_forfait_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=6
        )
        assert out == reel

    def test_conserve_autres_mois(self):
        prevu = [_prevu(6, 4)]
        reel = [_jour(5, 10, 1)]
        out = reel_forfait_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=6
        )
        assert any(j.get("mois") == 5 for j in out)
        assert any(j.get("mois") == 6 for j in out)
