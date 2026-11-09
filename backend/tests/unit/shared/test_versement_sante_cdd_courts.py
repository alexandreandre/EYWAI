"""CDD courts : versement santé signalé, dispense de prévoyance dite sur la fiche (R-391)."""

from __future__ import annotations

import pytest

from app.shared.domain.dispense_mutuelle import alerte_versement_sante
from app.shared.domain.prevoyance_obligatoire import _PLASTURGIE_SANS_PREVOYANCE

pytestmark = pytest.mark.unit

DISPENSE = {"adhesion": False, "dispense": {"motif": "cdd_moins_12_mois"}}


def test_cdd_de_trois_mois_dispense_est_signale():
    alerte = alerte_versement_sante(DISPENSE, "CDD", "2026-02-02", "2026-04-30")
    assert alerte is not None and "L911-7-1" in alerte and "Martine ne le" in alerte


def test_cdd_plus_long_rien():
    assert alerte_versement_sante(DISPENSE, "CDD", "2026-02-02", "2026-06-30") is None


def test_salarie_qui_adhere_rien():
    assert alerte_versement_sante({"adhesion": True}, "CDD", "2026-02-02", "2026-04-30") is None


def test_sans_dispense_rien():
    assert alerte_versement_sante({"adhesion": False}, "CDD", "2026-02-02", "2026-04-30") is None


def test_cdi_rien():
    assert alerte_versement_sante(DISPENSE, "CDI", "2026-02-02", "2026-04-30") is None


def test_dates_absentes_rien():
    assert alerte_versement_sante(DISPENSE, "CDD", "2026-02-02", None) is None


def test_dispense_de_prevoyance_non_cadre_dite_sur_la_fiche():
    assert "R242-1-6" in _PLASTURGIE_SANS_PREVOYANCE.fiche
