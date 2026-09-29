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


_PAGE_BRUT_NUL = "\n".join([
    "                  Rubriques                            Base          Taux salarial          Montant salarial             Mt patronal",
    "  MONTANT NET SOCIAL",
    "  NET A PAYER AVANT IMPOT SUR LE REVENU                                                                                                -419.75",
    "             Impôt sur le revenu                       Base                 Taux                  Montant                Cumul annuel",
    "Montant net imposable                                                                                                           2403.41",
    "Impôt sur le revenu prélevé à la source                      0.00                0.00                          0.00                0.00",
    "Montant net des heures compl/suppl exo.                                                                        0.00              454.98",
])


def test_un_net_imposable_seul_sous_cumul_annuel_est_le_cumul():
    """Mois entièrement en arrêt : le net imposable du mois est vide, seul le cumul
    annuel est imprimé ; le lire comme le montant du mois perdait le cumul."""
    b = Bulletin(matricule="ESSAI")
    lire_page(_PAGE_BRUT_NUL, 1, b)
    assert b.net["net_imposable"] == 0.0
    assert b.net["net_imposable_cumul"] == 2403.41
    assert b.net["net_hs_exo_cumul"] == 454.98
