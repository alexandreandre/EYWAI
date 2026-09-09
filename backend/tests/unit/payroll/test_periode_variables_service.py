"""Résolution de la fenêtre : règle société, surcharge, continuité."""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.unit

COLORPLAST = {"id": "c1", "paie_jour_de_fin": 4, "paie_occurrence": -2}
MAJI = {"id": "c2", "paie_jour_de_fin": 31, "paie_occurrence": -1}


@pytest.fixture()
def service(monkeypatch):
    from app.modules.payroll.application import periode_variables_service as svc

    surcharges: dict[tuple[str, int, int], dict] = {}
    societes = {"c1": COLORPLAST, "c2": MAJI}

    monkeypatch.setattr(
        svc, "get_variable_period", lambda cid, a, m: surcharges.get((cid, a, m))
    )
    monkeypatch.setattr(svc, "_charger_societe", lambda cid: societes[cid])
    svc._surcharges_de_test = surcharges
    return svc


def test_sans_surcharge_colorplast_juillet_suit_la_regle(service):
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 6, 22), date(2026, 7, 26))
    assert fenetre.origine == "regle"


def test_societe_en_mois_civil_na_pas_de_decalage(service):
    fenetre = service.resoudre_fenetre_variables("c2", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 7, 1), date(2026, 7, 31))


def test_la_surcharge_de_juillet_sapplique(service):
    service._surcharges_de_test[("c1", 2026, 7)] = {
        "start_date": "2026-06-22",
        "end_date": "2026-07-19",
        "origin": "manuel",
    }
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 7)
    assert (fenetre.debut, fenetre.fin) == (date(2026, 6, 22), date(2026, 7, 19))
    assert fenetre.origine == "manuel"


def test_aout_reprend_ou_juillet_sest_arrete(service):
    """Cartol : juillet arrêté au 19, août doit commencer le 20."""
    service._surcharges_de_test[("c1", 2026, 7)] = {
        "start_date": "2026-06-22",
        "end_date": "2026-07-19",
        "origin": "manuel",
    }
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 8)
    assert fenetre.debut == date(2026, 7, 20)
    assert fenetre.fin == date(2026, 8, 23)


def test_apercu_expose_les_semaines_et_le_mois_civil(service):
    apercu = service.apercu_fenetre("c1", 2026, 7)
    assert apercu["debut"] == "2026-06-22"
    assert apercu["fin"] == "2026-07-26"
    assert apercu["semaines"] == [26, 27, 28, 29, 30]
    assert apercu["mois_civil"] == ["2026-07-01", "2026-07-31"]
    assert apercu["report_debut"] == "2026-07-27"


def test_janvier_va_chercher_decembre_de_lannee_precedente(service):
    """Le passage d'année : janvier reprend là où décembre s'est arrêté."""
    service._surcharges_de_test[("c1", 2025, 12)] = {
        "start_date": "2025-11-24",
        "end_date": "2025-12-21",
        "origin": "manuel",
    }
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 1)
    assert fenetre.debut == date(2025, 12, 22)


def test_janvier_sans_surcharge_suit_la_regle_de_decembre(service):
    fenetre = service.resoudre_fenetre_variables("c1", 2026, 1)
    assert fenetre.debut.year == 2025
    assert fenetre.debut.month == 12
    assert fenetre.fin.month == 1
