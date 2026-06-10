"""Tests des règles métier prêts employeur."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.employee_loans.domain.rules import (
    build_amortization_schedule,
    compute_interest_benefit_in_kind,
    compute_interest_paid,
    compute_loan_repayment_cap,
    compute_monthly_payment,
    compute_repayment_amount,
    is_installment_fully_paid,
    requires_2062,
)


def test_requires_2062_threshold():
    assert requires_2062(Decimal("4999.99")) is False
    assert requires_2062(Decimal("5000")) is True
    assert requires_2062(Decimal("10000")) is True


def test_compute_monthly_payment_zero_rate():
    payment = compute_monthly_payment(Decimal("1200"), Decimal("0"), 12)
    assert payment == Decimal("100.00")


def test_compute_monthly_payment_with_rate():
    payment = compute_monthly_payment(Decimal("10000"), Decimal("0.05"), 12)
    assert payment > Decimal("850")
    assert payment < Decimal("860")


def test_build_amortization_schedule_zero_rate():
    monthly, lines = build_amortization_schedule(
        Decimal("1200"), Decimal("0"), 12, date(2026, 1, 1)
    )
    assert monthly == Decimal("100.00")
    assert len(lines) == 12
    assert lines[-1].remaining_capital == Decimal("0.00")
    assert sum(line.capital_part for line in lines) == Decimal("1200.00")


def test_build_amortization_schedule_with_interest():
    _, lines = build_amortization_schedule(
        Decimal("10000"), Decimal("0.05"), 12, date(2026, 3, 1)
    )
    assert len(lines) == 12
    assert lines[0].year == 2026 and lines[0].month == 3
    assert lines[0].interest_part > Decimal("0")
    assert lines[-1].remaining_capital == Decimal("0.00")


def test_compute_interest_benefit_in_kind_zero_loan_rate():
    legal = Decimal("0.0352")
    benefit = compute_interest_benefit_in_kind(
        Decimal("10000"), legal, Decimal("0")
    )
    expected = Decimal("10000") * legal / Decimal("12")
    assert benefit == expected.quantize(Decimal("0.01"))


def test_compute_interest_benefit_in_kind_no_benefit_when_rate_equals_legal():
    legal = Decimal("0.0352")
    benefit = compute_interest_benefit_in_kind(
        Decimal("10000"), legal, legal
    )
    assert benefit == Decimal("0.00")


def test_compute_repayment_amount_respects_seizable_cap():
    due = Decimal("500")
    seizable = Decimal("200")
    assert compute_repayment_amount(due, seizable) == Decimal("200.00")


def test_compute_repayment_amount_respects_remaining_capital():
    due = Decimal("500")
    seizable = Decimal("1000")
    remaining = Decimal("150")
    assert compute_repayment_amount(due, seizable, remaining) == Decimal("150.00")


def test_compute_interest_paid_proportional():
    assert compute_interest_paid(
        Decimal("400"), Decimal("40"), Decimal("200")
    ) == Decimal("20.00")
    assert compute_interest_paid(
        Decimal("400"), Decimal("40"), Decimal("400")
    ) == Decimal("40.00")


def test_is_installment_fully_paid():
    assert is_installment_fully_paid(
        Decimal("500"), Decimal("10"), Decimal("500"), Decimal("10"), Decimal("0")
    )
    assert not is_installment_fully_paid(
        Decimal("500"), Decimal("10"), Decimal("200"), Decimal("4"), Decimal("300")
    )
    assert is_installment_fully_paid(
        Decimal("500"), Decimal("10"), Decimal("150"), Decimal("0"), Decimal("0")
    )


def test_compute_loan_repayment_cap_uses_seizable_rules():
    cap = compute_loan_repayment_cap(Decimal("2500"))
    assert cap > Decimal("0")
    assert cap < Decimal("2500")
