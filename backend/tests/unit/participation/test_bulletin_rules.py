"""Tests unitaires — règles bulletin d'option participation."""

from __future__ import annotations

from decimal import Decimal

from app.modules.participation.domain.bulletin_rules import (
    compute_net_after_advances,
    compute_participation_csg,
    payroll_flags_for_amount,
    split_amount_by_choice,
)


class TestComputeParticipationCsg:
    def test_zero_gross(self):
        non_ded, ded, total = compute_participation_csg(0)
        assert non_ded == Decimal("0")
        assert ded == Decimal("0")
        assert total == Decimal("0")

    def test_cotte_example_approx(self):
        """Calage bulletin client COTTE : brut 3225.33."""
        non_ded, ded, total = compute_participation_csg(3225.33)
        assert non_ded == Decimal("93.53")
        assert ded == Decimal("219.32")
        assert total == Decimal("312.85")


class TestComputeNetAfterAdvances:
    def test_with_advance(self):
        non_ded, ded, net_before, net_final = compute_net_after_advances(3225.33, 1000)
        assert net_before == Decimal("2912.48")
        assert net_final == Decimal("1912.48")


class TestSplitAmountByChoice:
    def test_full_cash(self):
        split = split_amount_by_choice("full_cash", 1000)
        assert split.cash_amount == Decimal("1000.00")
        assert split.pee_amount == Decimal("0.00")

    def test_full_pee(self):
        split = split_amount_by_choice("full_pee", 500.5)
        assert split.cash_amount == Decimal("0.00")
        assert split.pee_amount == Decimal("500.50")

    def test_partial_cash(self):
        split = split_amount_by_choice("partial_cash", 1000, 300)
        assert split.cash_amount == Decimal("300.00")
        assert split.pee_amount == Decimal("700.00")


class TestPayrollFlags:
    def test_cash_taxed(self):
        assert payroll_flags_for_amount(True) == (True, True)

    def test_pee_exempt(self):
        assert payroll_flags_for_amount(False) == (False, False)
