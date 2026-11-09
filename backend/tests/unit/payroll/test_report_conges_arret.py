"""Reprise après un arrêt : l'information sur les congés (C. trav. L3141-19-1 à -3)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.report_conges_arret import (
    CODE_ALERTE_REPORT_CONGES,
    alerte_report_conges_apres_arret,
)

pytestmark = pytest.mark.unit

SOLDES = {"conges_payes": {"solde": 12.5}}


def _arret(debut="2026-08-03", fin="2026-10-12", type_="maladie_simple"):
    return {"arret_type": type_, "date_debut": debut, "date_fin": fin}


def test_arret_long_finissant_ce_mois_avec_des_conges():
    alerte = alerte_report_conges_apres_arret(_arret(), SOLDES, 2026, 10)
    assert alerte["code"] == CODE_ALERTE_REPORT_CONGES
    assert alerte["critique"] is False and alerte["severity"] == "warning"
    assert "12,5 jours" in alerte["message"] and "L3141-19-3" in alerte["message"]
    assert "15 mois" in alerte["message"]


def test_arret_qui_continue_le_mois_suivant_ne_dit_rien():
    assert alerte_report_conges_apres_arret(_arret(fin="2026-11-05"), SOLDES, 2026, 10) is None


def test_arret_court_ne_dit_rien():
    assert alerte_report_conges_apres_arret(_arret(debut="2026-10-01"), SOLDES, 2026, 10) is None


def test_sans_conges_restants_rien():
    assert alerte_report_conges_apres_arret(_arret(), {"conges_payes": {"solde": 0}}, 2026, 10) is None


@pytest.mark.parametrize("type_", ["mi_temps_therapeutique", "maternite"])
def test_hors_maladie_et_accident_rien(type_):
    assert alerte_report_conges_apres_arret(_arret(type_=type_), SOLDES, 2026, 10) is None


def test_plusieurs_arrets_le_dernier_qui_se_termine():
    arret = {
        **_arret(),
        "arrets_du_mois": [
            _arret(debut="2026-10-01", fin="2026-10-03"),
            _arret(debut="2026-09-01", fin="2026-10-28"),
        ],
    }
    assert "28/10/2026" in alerte_report_conges_apres_arret(arret, SOLDES, 2026, 10)["message"]


def test_accident_du_travail_compte():
    assert alerte_report_conges_apres_arret(_arret(type_="accident_travail"), SOLDES, 2026, 10)
