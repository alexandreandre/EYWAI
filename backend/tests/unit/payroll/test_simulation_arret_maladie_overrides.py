"""Tests des overrides what-if de la simulation d'arrêt maladie (parties pures)."""

from __future__ import annotations

from datetime import date

from app.modules.payroll.application.simulation_arret_maladie import (
    _hire_date_pour_anciennete,
)
from app.modules.payroll.engine.maintien_salaire_service import _mois_anciennete


class TestHireDatePourAnciennete:
    def test_roundtrip_anciennete(self):
        ref = date(2026, 6, 1)
        for mois in (0, 12, 47, 72, 132, 372):
            hire = _hire_date_pour_anciennete(ref, mois)
            assert _mois_anciennete(hire, ref) == mois

    def test_anciennete_negative_clampee(self):
        ref = date(2026, 6, 1)
        hire = _hire_date_pour_anciennete(ref, -5)
        assert _mois_anciennete(hire, ref) == 0
