"""Tests — affichage officiel des soldes (API)."""

from datetime import date

import pytest

from app.modules.absences.application.balance_display import (
    _official_balance_row,
    balances_to_api_list,
)
from app.modules.absences.domain.leave_policy import EmployeeLeaveAdjustment
from app.modules.absences.domain.rules import compute_absence_balances


class TestOfficialBalanceRow:
    def test_acquis_egale_pris_plus_restant(self):
        row = _official_balance_row({"acquis": 25.0, "pris": 6.5, "solde": 18.5})
        assert row["acquired"] == 25.0
        assert row["taken"] == 6.5
        assert row["remaining"] == 18.5

    def test_masque_droits_theoriques_quand_reprise_paie(self):
        """Reprise bulletin à 0 : acquis affiché = 0, pas les droits calculés."""
        row = _official_balance_row({"acquis": 3.0, "pris": 0.0, "solde": 0.0})
        assert row["acquired"] == 0.0
        assert row["taken"] == 0.0
        assert row["remaining"] == 0.0

    def test_rtt_coherent_apres_import(self):
        row = _official_balance_row({"acquis": 10.0, "pris": 0.0, "solde": 0.0})
        assert row["acquired"] == 0.0
        assert row["remaining"] == 0.0


class TestBalancesToApiList:
    def test_elsa_scenario_reprise_mai_2026(self):
        hire_date = date(2025, 4, 14)
        ref = date(2026, 6, 28)
        from app.modules.absences.domain.rules import compute_cp_period_balances

        sans = compute_cp_period_balances(hire_date, [], ref)
        n_remaining = float(sans["n_remaining"])
        adjustment = EmployeeLeaveAdjustment(
            cp_n_opening_balance=-n_remaining,
            cp_n1_opening_balance=-5.0,
            rtt_opening_balance=-10.0,
        )
        soldes = compute_absence_balances(
            hire_date, [], ref, adjustment=adjustment
        )
        soldes["rtt"] = {"acquis": 10.0, "pris": 0.0, "solde": 0.0}

        rows = balances_to_api_list(soldes)
        cp = next(r for r in rows if r["type"] == "Congés Payés")
        rtt = next(r for r in rows if r["type"] == "RTT")

        assert cp["acquired"] == cp["taken"] + cp["remaining"]
        assert rtt["acquired"] == rtt["taken"] + rtt["remaining"]
        assert rtt["remaining"] == 0.0
        assert rtt["acquired"] == 0.0

    def test_period_roll_after_bulletin_import(self):
        """Solde N importé en mai bascule en N-1 au 1er juin (pas remis à zéro)."""
        hire_date = date(2025, 4, 14)
        ref_mai = date(2026, 5, 31)
        ref_juin = date(2026, 6, 28)
        adjustment = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=-5.0,
            cp_n_opening_balance=-16.54,
            note="Import CP bulletin Mai 2026 (test.pdf)",
        )
        mai = compute_absence_balances(
            hire_date, [], ref_mai, adjustment=adjustment
        )
        juin = compute_absence_balances(
            hire_date, [], ref_juin, adjustment=adjustment
        )
        assert mai["conges_payes"]["solde"] == pytest.approx(13.46, abs=0.01)
        assert juin["conges_payes"]["solde"] == pytest.approx(13.46, abs=0.01)
        cp_juin = balances_to_api_list(juin)
        row = next(r for r in cp_juin if r["type"] == "Congés Payés")
        assert row["remaining"] == pytest.approx(13.5, abs=0.1)
        assert row["acquired"] == row["remaining"]
