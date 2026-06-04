"""Tests unitaires — taux PAS neutre."""

from __future__ import annotations

from app.modules.payroll.engine.calcul_net import taux_pas_neutre
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def test_taux_pas_neutre_tranche_basse():
    baremes_pas = baremes_snapshot()["pas"]
    assert taux_pas_neutre(baremes_pas, 1500.0, "metropole") == 0.0


def test_taux_pas_neutre_tranche_haute():
    baremes_pas = baremes_snapshot()["pas"]
    taux = taux_pas_neutre(baremes_pas, 5000.0, "metropole")
    assert taux == 11.0


def test_taux_pas_neutre_bareme_vide():
    assert taux_pas_neutre([], 2000.0) == 0.0
