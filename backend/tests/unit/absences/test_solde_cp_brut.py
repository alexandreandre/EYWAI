"""Le solde N non raboté reste disponible pour les reprises."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.domain.rules import compute_cp_period_balances

pytestmark = pytest.mark.unit


def test_le_solde_n_brut_garde_son_signe():
    conges = [{"type": "conge_paye", "status": "validated", "jours_payes": 10.0,
               "selected_days": [f"2026-08-{j:02d}" for j in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]}]
    soldes = compute_cp_period_balances(date(2026, 6, 1), conges, date(2026, 8, 31))
    assert soldes["n_remaining"] == 0.0
    assert soldes["n_remaining_brut"] < 0
    assert soldes["n_remaining_brut"] == round(soldes["periode_courante"]["acquis"] - 10.0, 2)
