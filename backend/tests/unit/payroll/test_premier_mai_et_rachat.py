"""Alertes d'avant-paie du 1er mai travaillé et du rachat de jours (R-395, R-396)."""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.controles_convention import (
    controle_premier_mai_travaille,
    controle_rachat_de_jours,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _contexte(evenements, **kw):
    contexte = build_test_contexte(salaire_base=2275.05)
    contexte.evenements_paie = evenements
    return contexte


def _ev(date_complete, heures=3.67, type_ev="travail_base", **extra):
    return {"date_complete": date_complete, "heures": heures, "type": type_ev, **extra}


def test_heures_pointees_le_premier_mai_declenchent_l_alerte():
    alertes = controle_premier_mai_travaille(_contexte([_ev("2026-05-01"), _ev("2026-05-04", 7.0)]))
    assert len(alertes) == 1
    alerte = alertes[0]
    assert alerte["code"] == "premier_mai_travaille"
    assert alerte["critique"] is False and alerte["severity"] == "warning"
    assert "3 h 40" in alerte["message"] or "3,67" in alerte["message"]
    assert "L3133-6" in alerte["message"]


def test_autre_jour_ferie_pas_d_alerte():
    assert controle_premier_mai_travaille(_contexte([_ev("2026-05-08"), _ev("2026-07-14")])) == []


def test_premier_mai_chome_pas_d_alerte():
    assert controle_premier_mai_travaille(_contexte([_ev("2026-05-01", 7.0, "ferie")])) == []


def test_repli_de_planning_n_est_pas_un_pointage():
    assert controle_premier_mai_travaille(_contexte([_ev("2026-05-01", source_repli_planning=True)])) == []


def test_forfait_jours_sur_le_jour_lu_dans_jour_mois():
    contexte = SimpleNamespace(
        evenements_paie=[{"jour": 1, "mois": 5, "annee": 2026, "type": "travail_base", "heures": 1.0}],
        is_forfait_jour=True,
    )
    alertes = controle_premier_mai_travaille(contexte, 2026)
    assert "Jour travaillé le 1er mai" in alertes[0]["message"]


@pytest.mark.parametrize("libelle", ["Rachat de jours de repos", "Rachat RTT", "Rachat jours forfait"])
def test_rachat_de_jours_signale(libelle):
    alertes = controle_rachat_de_jours([{"libelle": libelle, "gain": 500.0}])
    assert alertes[0]["code"] == "rachat_de_jours_sans_regime"
    assert alertes[0]["critique"] is False
    assert "Martine ne sait pas" in alertes[0]["message"]
    assert "L3121-59" in alertes[0]["message"]


@pytest.mark.parametrize(
    "ligne",
    [
        {"libelle": "Salaire de base", "gain": 2000.0},
        {"libelle": "Rachat CET", "gain": 100.0},
        {"libelle": "Rachat de jours", "gain": 0.0},
    ],
)
def test_pas_d_alerte_hors_rachat_de_jours(ligne):
    assert controle_rachat_de_jours([ligne]) == []
