"""Tests de bornes_periode_de_paie (fonction pure, sans ContextePaie)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie

pytestmark = pytest.mark.unit


def test_arrete_glissant_juillet_2026():
    """(4, -2) = avant-dernier vendredi, fin le dimanche de sa semaine :
    juillet 2026 = 22/06 → 26/07 (le cas Barberet : un CDD finissant le
    30/06 est payé sur juillet)."""
    debut, fin = bornes_periode_de_paie(2026, 7, 4, -2)
    assert (debut, fin) == (date(2026, 6, 22), date(2026, 7, 26))


def test_arrete_glissant_septembre_2026():
    debut, fin = bornes_periode_de_paie(2026, 9, 4, -2)
    assert (debut, fin) == (date(2026, 8, 24), date(2026, 9, 20))


def test_mois_calendaire():
    """jour_de_fin hors [0, 6] → mois civil plein."""
    debut, fin = bornes_periode_de_paie(2026, 7, 31, -1)
    assert (debut, fin) == (date(2026, 7, 1), date(2026, 7, 31))


def test_pavage_sans_trou_ni_recouvrement():
    """La période de M+1 commence le lendemain de la fin de M."""
    _, fin_juillet = bornes_periode_de_paie(2026, 7, 4, -2)
    debut_aout, _ = bornes_periode_de_paie(2026, 8, 4, -2)
    assert (debut_aout - fin_juillet).days == 1
