"""Tests du diagnostic d'équilibre OD (balance_debug)."""

import pytest

from app.modules.exports.infrastructure.payroll_ledger import _BalanceTracker

pytestmark = pytest.mark.unit


class TestBalanceTracker:
    def test_finalize_debit_heavier(self):
        tracker = _BalanceTracker()
        tracker.add_debit("salaire_brut", 10000.0)
        tracker.add_debit("charges_patronales", 3000.0)
        tracker.add_credit("net_a_payer", 7000.0)
        tracker.add_credit("cotisations_salariales", 2000.0)

        result = tracker.finalize(
            payslips_count=2,
            ecritures_lines=4,
            payslip_source_totals={"total_brut": 10000.0, "employees_count": 2},
            period="2026-06",
        )

        assert result["total_debit"] == 13000.0
        assert result["total_credit"] == 9000.0
        assert result["ecart"] == 4000.0
        assert result["heavier_side"] == "debit"
        assert "Excédent de débit" in result["interpretation"]
        assert "gap_analysis" in result
        assert result["gap_analysis"]["salary_equation"]["brut_bulletins"] == 10000.0

    def test_tracks_skipped_entries(self):
        tracker = _BalanceTracker()
        tracker.skip("pas non posté (100€) : mapping manquant")
        result = tracker.finalize(
            payslips_count=1,
            ecritures_lines=0,
            payslip_source_totals={},
            period="2026-06",
        )
        assert result["skipped_entries"] == ["pas non posté (100€) : mapping manquant"]
