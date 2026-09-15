"""Déduction forfaitaire patronale sur les heures sup : l'arrondi du cabinet.

Sous 20 salariés, l'employeur déduit 1,50 € par heure supplémentaire. Les
salariés de Colorplast sont à 39 h, soit 17,33 h structurelles par mois :
17,33 × 1,50 = 25,995. Quadra imprime 26,00 ; nous imprimions 25,99, sur les
cinq bulletins de février 2026 et sur ceux de janvier.

Deux causes cumulées, d'où le calcul en décimal : `round` de Python retient le
pair le plus proche (25,99 plutôt que 26,00), et 17,33 × 1,50 vaut de toute
façon 25,994999999999997 en binaire, ce qui ferait basculer n'importe quel
arrondi vers le bas.

Valeurs relevées sur les bulletins Quadra de février 2026 (env. de test).
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import _produit_arrondi_centime

pytestmark = pytest.mark.unit

MONTANT_PAR_HEURE = 1.50

#: (heures sup du mois, déduction imprimée par Quadra). Bugny, Cotte et Girerd
#: n'ont que leurs 17,33 h structurelles ; Gautheron y ajoute 3,5 h payées,
#: Espinosa 19 h.
BULLETINS_FEVRIER = [
    ("BUGNY", 17.33, 26.00),
    ("COTTE", 17.33, 26.00),
    ("ESPINOSA", 36.33, 54.50),
    ("GAUTHERON", 20.83, 31.25),
    ("GIRERD", 17.33, 26.00),
]


@pytest.mark.parametrize("nom, heures, attendu", BULLETINS_FEVRIER)
def test_deduction_suit_l_arrondi_du_cabinet(nom, heures, attendu):
    assert _produit_arrondi_centime(heures, MONTANT_PAR_HEURE) == attendu


def test_la_moitie_s_eloigne_de_zero():
    """Le demi-centime monte, il ne redescend pas vers le pair le plus proche."""
    assert _produit_arrondi_centime(0.03, 0.5) == 0.02  # 0,015 → 0,02
    assert _produit_arrondi_centime(0.05, 0.5) == 0.03  # 0,025 → 0,03


def test_un_produit_exact_reste_intact():
    assert _produit_arrondi_centime(12.0, MONTANT_PAR_HEURE) == 18.00
