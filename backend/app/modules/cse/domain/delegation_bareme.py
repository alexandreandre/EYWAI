# app/modules/cse/domain/delegation_bareme.py
"""
Barème légal des heures de délégation CSE — art. R. 2314-1 du Code du travail.
Source de vérité immuable (loi), identique pour tous les tenants.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class BaremeRow:
    """Une tranche d'effectif du barème R. 2314-1."""

    effectif_min: int
    effectif_max: int
    nb_titulaires: int
    heures_mensuelles_titulaire: float


# Barème complet art. R. 2314-1 (effectif, titulaires, h/mois/titulaire)
BAREME_R2314_1: Tuple[BaremeRow, ...] = (
    BaremeRow(11, 24, 1, 10),
    BaremeRow(25, 49, 2, 10),
    BaremeRow(50, 74, 4, 18),
    BaremeRow(75, 99, 5, 19),
    BaremeRow(100, 124, 6, 21),
    BaremeRow(125, 149, 7, 21),
    BaremeRow(150, 174, 8, 21),
    BaremeRow(175, 199, 9, 21),
    BaremeRow(200, 249, 10, 22),
    BaremeRow(250, 299, 11, 22),
    BaremeRow(300, 399, 11, 22),
    BaremeRow(400, 499, 12, 22),
    BaremeRow(500, 599, 13, 24),
    BaremeRow(600, 699, 14, 24),
    BaremeRow(700, 799, 14, 24),
    BaremeRow(800, 899, 15, 24),
    BaremeRow(900, 999, 16, 24),
    BaremeRow(1000, 1249, 17, 24),
    BaremeRow(1250, 1499, 18, 24),
    BaremeRow(1500, 1749, 20, 26),
    BaremeRow(1750, 1999, 21, 26),
    BaremeRow(2000, 2249, 22, 26),
    BaremeRow(2250, 2499, 23, 26),
    BaremeRow(2500, 2749, 24, 26),
    BaremeRow(2750, 2999, 24, 26),
    BaremeRow(3000, 3249, 25, 26),
    BaremeRow(3250, 3499, 25, 26),
    BaremeRow(3500, 3749, 26, 27),
    BaremeRow(3750, 3999, 26, 27),
    BaremeRow(4000, 4249, 26, 28),
    BaremeRow(4250, 4499, 27, 28),
    BaremeRow(4500, 4749, 27, 28),
    BaremeRow(4750, 4999, 28, 28),
    BaremeRow(5000, 5249, 29, 29),
    BaremeRow(5250, 5499, 29, 29),
    BaremeRow(5500, 5749, 29, 29),
    BaremeRow(5750, 5999, 30, 29),
    BaremeRow(6000, 6249, 31, 29),
    BaremeRow(6250, 6499, 31, 29),
    BaremeRow(6500, 6749, 31, 29),
    BaremeRow(6750, 6999, 31, 30),
    BaremeRow(7000, 7249, 32, 30),
    BaremeRow(7250, 7499, 32, 30),
    BaremeRow(7500, 7749, 32, 31),
    BaremeRow(7750, 7999, 32, 32),
    BaremeRow(8000, 8249, 32, 32),
    BaremeRow(8250, 8499, 33, 32),
    BaremeRow(8500, 8749, 33, 32),
    BaremeRow(8750, 8999, 33, 32),
    BaremeRow(9000, 9249, 34, 32),
    BaremeRow(9250, 9499, 34, 32),
    BaremeRow(9500, 9749, 34, 32),
    BaremeRow(9750, 9999, 34, 34),
    BaremeRow(10000, 999999, 35, 34),
)

TITULAIRE_ROLES = frozenset({"titulaire", "secretaire", "tresorier"})
ZERO_CREDIT_ROLES = frozenset({"suppleant", "autre"})

PLAFOND_MULTIPLIER = 1.5
REPORT_WINDOW_MONTHS = 12
EMPLOYER_NOTICE_DAYS = 8


def lookup_bareme_row(reference_headcount: int) -> Optional[BaremeRow]:
    """Retourne la tranche barème pour un effectif de référence, ou None si < 11."""
    if reference_headcount < 11:
        return None
    for row in BAREME_R2314_1:
        if row.effectif_min <= reference_headcount <= row.effectif_max:
            return row
    return None


def heures_mensuelles_legales(reference_headcount: int) -> float:
    """Heures mensuelles par titulaire selon l'effectif (0 si effectif < 11)."""
    row = lookup_bareme_row(reference_headcount)
    return float(row.heures_mensuelles_titulaire) if row else 0.0
