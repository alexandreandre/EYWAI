"""Tests unitaires — calcul_frais."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_frais import (
    appliquer_exoneration_note_frais,
    exoneration_repas,
    indemnite_km,
    reintegration_exces,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def test_exoneration_repas():
    frais = baremes_snapshot()["frais_pro"]
    assert exoneration_repas(frais) == 21.1


def test_reintegration_exces():
    assert reintegration_exces(30.0, 21.1) == pytest.approx(8.9, abs=0.01)


def test_indemnite_km_voiture():
    km = baremes_snapshot()["baremes_km"]
    val = indemnite_km(km, "voitures", 3, 100.0)
    assert val == pytest.approx(52.9, abs=0.1)


def test_appliquer_exoneration_note_frais():
    frais = baremes_snapshot()["frais_pro"]
    exo, reint, plafond = appliquer_exoneration_note_frais(
        {"montant": 30.0, "type": "repas"}, frais
    )
    assert plafond == 21.1
    assert exo == 21.1
    assert reint == pytest.approx(8.9, abs=0.01)
