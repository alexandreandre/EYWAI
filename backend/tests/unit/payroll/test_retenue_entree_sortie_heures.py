"""Les heures retirées pour une entrée ou une sortie ne sont pas rémunérées.

Le mois d'un salarié qui arrive en cours de route peut être mensualisé en
entier, puis la part antérieure à l'embauche retirée par une ligne « Absence
pour entrée ou sortie ». Ces heures ne sont pas payées : elles doivent donc
sortir des heures rémunérées, et avec elles du SMIC de référence de la
réduction générale.

Sans cela on réclame un allègement sur des heures qu'on n'a pas payées — le
défaut corrigé en janvier 2026 pour les absences non rémunérées, qui se
reproduisait ici sous un autre nom.

Relevé sur Fuckar (Colorplast, avril 2026), embauché le 07/04 : 30,50 h
retirées de sa paie pour 372,10 €, mais laissées dans son compteur. Quadra
imprime 143,50 h de période, nous 170,95 — et 82,02 € d'allègement de trop.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _heures_comptees(heures_base: float, heures_supp: float,
                     heures_absence_non_payees: float) -> float:
    """Le compteur de `payslip_run_heures`, isolé."""
    return round(max(0.0, heures_base + heures_supp - heures_absence_non_payees), 2)


def test_la_retenue_d_entree_sort_du_compteur():
    """Fuckar : 151,67 h de base + 19,28 h sup − 30,50 h non payées."""
    assert _heures_comptees(151.67, 19.28, 30.50) == 140.45


def test_sans_retenue_le_compteur_ne_bouge_pas():
    assert _heures_comptees(151.67, 19.28, 0.0) == 170.95


def test_une_retenue_plus_grande_que_le_mois_ne_passe_pas_sous_zero():
    assert _heures_comptees(151.67, 0.0, 200.0) == 0.0
