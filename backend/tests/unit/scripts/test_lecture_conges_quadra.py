"""Lecture du bloc de congés d'un bulletin Quadra, soldes négatifs compris."""

from __future__ import annotations

import pytest

from scripts.backtest.colorplast_lignes_quadra import Bulletin, lire_page

pytestmark = pytest.mark.unit

_BLOC = """                  CP N-1         CP N
  Acquis :          3.33 /       6.24 /
  Total pris :      3.33 /       6.67 /                                           1 rue Essai
  Solde :           0.00 /      -0.43 /
"""


def test_un_solde_negatif_garde_son_signe():
    b = Bulletin(matricule="ESSAI")
    lire_page(_BLOC, 1, b)
    assert b.cp["Solde"] == (0.0, -0.43)
    assert b.cp["Acquis"] == (3.33, 6.24)
    assert b.cp["Total pris"] == (3.33, 6.67)
