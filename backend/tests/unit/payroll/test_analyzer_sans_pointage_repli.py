"""Absences fictives évitées quand un mois sans pointage est replié sur le planning."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.modules.payroll.application.analyzer import (
    _metadata_for_aggregated_event,
    analyser_horaires_du_mois,
)
from app.modules.payroll.documents.payslip_run_heures import (
    _extraire_arret_pour_maintien,
)
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
    def test_preserve_maintien_base_ouvree_sur_arret(self):
        meta = _metadata_for_aggregated_event(
            [
                {
                    "mois": 3,
                    "jour": 26,
                    "type": "arret_maladie",
                    "maintien_base_ouvree": True,
                }
            ],
            3,
            26,
            "arret_maladie",
        )

        assert meta["maintien_base_ouvree"] is True

    def test_transmet_maintien_base_ouvree_au_calcul(self):
        arret = _extraire_arret_pour_maintien(
            [
                {
                    "date_complete": "2026-03-26",
                    "type": "arret_maladie",
                    "arret_type": "maladie_simple",
                    "maintien_base_ouvree": True,
                }
            ],
            SimpleNamespace(contrat={"contrat": {"temps_travail": {}}}),
            date(2026, 3, 1),
            date(2026, 3, 31),
        )

        assert arret is not None
        assert arret["maintien_base_ouvree"] is True

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

    def test_repli_planning_ne_cree_pas_heures_supplementaires(self):
        prevu = [
            _prevu(6, jour, heures)
            for jour, heures in zip(
                (1, 2, 3, 4, 5),
                (7.8333, 7.8333, 7.8333, 7.8333, 3.75),
                strict=True,
            )
        ]
        actual = reel_heures_avec_repli_planning_si_sans_pointage(
            prevu, [], annee=2026, mois=6
        )

        events = analyser_horaires_du_mois(
            prevu, actual, 35.0, 2026, 6, "Lucas ALVES"
        )

        assert not any(e.get("type") in {"travail_hs25", "travail_hs50"} for e in events)


def test_analyzer_conserve_un_week_end_porteur_des_bornes_d_arret():
    """Un samedi d'arrêt (type weekend, 0 h) doit atteindre le bulletin s'il
    porte date_*_arret_reel — sinon un mois de débordement week-end perd
    prévoyance/IJSS. Un week-end ordinaire reste filtré."""
    planned = [
        {
            "annee": 2026,
            "mois": 8,
            "jour": 1,
            "type": "weekend",
            "heures_prevues": 0,
            "arret_type": "maladie_simple",
            "date_debut_arret_reel": "2026-07-31",
            "date_fin_arret_reel": "2026-08-02",
        },
        {
            "annee": 2026,
            "mois": 8,
            "jour": 2,
            "type": "weekend",
            "heures_prevues": 0,
        },
        {
            "annee": 2026,
            "mois": 8,
            "jour": 3,
            "type": "travail",
            "heures_prevues": 7.0,
        },
    ]
    events = analyser_horaires_du_mois(planned, [], 35.0, 2026, 8, "Test")
    par_jour = {e["jour"]: e for e in events}
    assert par_jour[1]["type"] == "weekend"
    assert par_jour[1]["heures"] == 0
    assert par_jour[1]["date_fin_arret_reel"] == "2026-08-02"
    assert 2 not in par_jour
