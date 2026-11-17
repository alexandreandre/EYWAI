"""Derniers trous du forfait jours, comblés le 17/11 (test de parité).

- premier mois après une reprise : la période du forfait déborde sur le mois
  payé par l'ancien logiciel (21/09 → 25/10 pour octobre) ; ses absences en
  sortent, comme aux heures ;
- variables automatiques avant le bulletin : une fonction pour les deux
  générateurs, jamais en bac à sable, un échec dit sur le bulletin.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.documents import variables_automatiques as va
from app.modules.payroll.documents.payslip_run_forfait import absences_hors_reprise
from app.modules.payroll.engine import replis

pytestmark = pytest.mark.unit

FIN_SEPTEMBRE = date(2026, 9, 30)


def _jour(iso: str, type_jour: str, **extra) -> dict:
    return {"date_complete": iso, "type": type_jour, "heures": 1.0, **extra}


def test_les_absences_du_mois_repris_sortent_de_la_periode_du_forfait():
    periode = [
        _jour("2026-09-28", "conges_payes"),
        _jour("2026-09-29", "arret_maladie"),
        _jour("2026-09-30", "travail_base"),
        _jour("2026-09-30", "absence_non_remuneree", is_regularisation_anterieure=True),
        _jour("2026-10-01", "arret_maladie"),
    ]
    gardes = absences_hors_reprise(periode, FIN_SEPTEMBRE)
    assert [(j["date_complete"], j["type"]) for j in gardes] == [
        ("2026-09-30", "travail_base"),
        ("2026-09-30", "absence_non_remuneree"),
        ("2026-10-01", "arret_maladie"),
    ]


def test_hors_du_premier_mois_rien_ne_sort():
    periode = [_jour("2026-10-20", "conges_payes")]
    assert absences_hors_reprise(periode, None) == periode


class _Reglages:
    def __init__(self, allume: bool):
        self.allume = allume

    def get_company_planning_settings(self, _company_id):
        return {"auto_generate_payroll_variables_before_payslip": self.allume}


@pytest.fixture
def appels(monkeypatch):
    faits: list[tuple] = []
    from app.modules.payroll_variables.application import generate_monthly

    monkeypatch.setattr(
        generate_monthly,
        "generate_monthly_variables",
        lambda *a, **k: faits.append((a, k)),
    )
    return faits


def _reglage(monkeypatch, allume: bool):
    from app.modules.planning.infrastructure import repository

    monkeypatch.setattr(repository, "planning_repository", _Reglages(allume))


@pytest.mark.parametrize("en_bac_a_sable", [False, True])
def test_variables_automatiques_seulement_hors_bac_a_sable(monkeypatch, appels, en_bac_a_sable):
    _reglage(monkeypatch, True)
    va.variables_automatiques_avant_bulletin(
        "c1", "e1", 2026, 10, en_bac_a_sable=en_bac_a_sable, contract_period_id=None
    )
    assert len(appels) == (0 if en_bac_a_sable else 1)
    if appels:
        assert appels[0][1] == {"dry_run": False, "employee_id": "e1"}


def test_reglage_eteint_rien_n_est_ecrit(monkeypatch, appels):
    _reglage(monkeypatch, False)
    va.variables_automatiques_avant_bulletin(
        "c1", "e1", 2026, 10, en_bac_a_sable=False, contract_period_id=None
    )
    assert appels == []


def test_un_echec_est_dit_sur_le_bulletin(monkeypatch):
    class _Panne:
        def get_company_planning_settings(self, _c):
            raise RuntimeError("base indisponible")

    from app.modules.planning.infrastructure import repository

    monkeypatch.setattr(repository, "planning_repository", _Panne())
    notes: list = []
    jeton = replis.ouvrir_collecte(notes)
    try:
        va.variables_automatiques_avant_bulletin(
            "c1", "e1", 2026, 10, en_bac_a_sable=False, contract_period_id=None
        )
    finally:
        replis.fermer_collecte(jeton)
    assert notes, "le repli doit être noté"
