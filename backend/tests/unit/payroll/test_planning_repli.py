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


class TestRepliPlanningHeures:
    def _prevu_heures(self, mois: int, jour: int, heures: float, *, annee: int = 2026):
        return {
            "annee": annee,
            "mois": mois,
            "jour": jour,
            "type": "travail",
            "heures_prevues": heures,
        }

    def test_sans_pointage_reprend_heures_prevues(self):
        from app.modules.payroll.planning_repli import (
            reel_heures_avec_repli_planning_si_sans_pointage,
        )

        prevu = [self._prevu_heures(4, 21, 8.0), self._prevu_heures(4, 22, 8.0)]
        reel = [_jour(5, 3, 7.0)]
        out = reel_heures_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=4
        )
        avril = [j for j in out if j.get("mois") == 4]
        assert len(avril) == 2
        assert avril[0]["heures_faites"] == 8.0
        assert avril[0].get("source_repli_planning") is True

    def test_avec_pointage_inchange(self):
        from app.modules.payroll.planning_repli import (
            reel_heures_avec_repli_planning_si_sans_pointage,
        )

        prevu = [self._prevu_heures(4, 21, 8.0)]
        reel = [_jour(4, 21, 7.5)]
        out = reel_heures_avec_repli_planning_si_sans_pointage(
            prevu, reel, annee=2026, mois=4
        )
        assert out == reel

    def test_appliquer_repli_par_mois(self):
        from app.modules.payroll.planning_repli import (
            appliquer_repli_sans_pointage_par_mois,
        )

        prevu = [self._prevu_heures(4, 21, 8.0), self._prevu_heures(5, 5, 7.0)]
        reel = [_jour(5, 5, 7.0)]
        out = appliquer_repli_sans_pointage_par_mois(
            prevu, reel, [(2026, 4), (2026, 5)], is_forfait_jour=False
        )
        assert any(
            j.get("mois") == 4 and j.get("heures_faites") == 8.0 for j in out
        )
        assert any(j.get("mois") == 5 and j.get("heures_faites") == 7.0 for j in out)
