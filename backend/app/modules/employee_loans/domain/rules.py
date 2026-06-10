"""
Règles métier pures — prêts employeur.

Aucune dépendance FastAPI / Supabase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from app.modules.employee_loans.domain.constants import DECLARATION_2062_THRESHOLD_EUR
from app.modules.saisies_avances.domain.rules import calculate_seizable_amount


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def requires_2062(principal: Decimal) -> bool:
    """Prêt ≥ 5 000 € : déclaration formulaire 2062."""
    return principal >= DECLARATION_2062_THRESHOLD_EUR


def compute_monthly_payment(
    principal: Decimal, annual_rate: Decimal, duration_months: int
) -> Decimal:
    """Mensualité constante (amortissement français)."""
    if duration_months <= 0:
        raise ValueError("La durée doit être d'au moins 1 mois.")
    if principal <= 0:
        raise ValueError("Le capital doit être strictement positif.")
    if annual_rate <= 0:
        return _money(principal / Decimal(duration_months))

    monthly_rate = annual_rate / Decimal("12")
    factor = (Decimal("1") + monthly_rate) ** duration_months
    payment = principal * monthly_rate * factor / (factor - Decimal("1"))
    return _money(payment)


@dataclass(frozen=True)
class AmortizationLine:
    installment_number: int
    year: int
    month: int
    capital_part: Decimal
    interest_part: Decimal
    total_due: Decimal
    remaining_capital: Decimal


def _add_months(start: date, offset: int) -> tuple[int, int]:
    total = (start.year * 12 + (start.month - 1)) + offset
    return total // 12, (total % 12) + 1


def build_amortization_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    duration_months: int,
    start_date: date,
) -> tuple[Decimal, List[AmortizationLine]]:
    """Construit l'échéancier d'amortissement prévisionnel."""
    monthly_payment = compute_monthly_payment(principal, annual_rate, duration_months)
    remaining = principal
    monthly_rate = annual_rate / Decimal("12") if annual_rate > 0 else Decimal("0")
    lines: List[AmortizationLine] = []

    for i in range(duration_months):
        year, month = _add_months(start_date, i)
        if monthly_rate > 0:
            interest_part = _money(remaining * monthly_rate)
            capital_part = _money(min(remaining, monthly_payment - interest_part))
            if i == duration_months - 1:
                capital_part = _money(remaining)
                total_due = _money(capital_part + interest_part)
            else:
                total_due = monthly_payment
        else:
            interest_part = Decimal("0.00")
            capital_part = _money(
                remaining if i == duration_months - 1 else principal / Decimal(duration_months)
            )
            total_due = capital_part

        remaining = _money(max(Decimal("0"), remaining - capital_part))
        lines.append(
            AmortizationLine(
                installment_number=i + 1,
                year=year,
                month=month,
                capital_part=capital_part,
                interest_part=interest_part,
                total_due=total_due,
                remaining_capital=remaining,
            )
        )

    return monthly_payment, lines


def compute_interest_benefit_in_kind(
    remaining_capital: Decimal,
    legal_annual_rate: Decimal,
    actual_annual_rate: Decimal,
) -> Decimal:
    """
    Avantage en nature mensuel = intérêts au taux légal − intérêts réellement facturés.
    """
    if remaining_capital <= 0:
        return Decimal("0.00")
    legal_monthly = remaining_capital * legal_annual_rate / Decimal("12")
    actual_monthly = remaining_capital * actual_annual_rate / Decimal("12")
    benefit = legal_monthly - actual_monthly
    return _money(max(Decimal("0"), benefit))


def compute_loan_repayment_cap(
    net_salary: Decimal,
    dependents_count: int = 0,
) -> Decimal:
    """Plafond de retenue sur le net (fraction saisissable)."""
    return calculate_seizable_amount(net_salary, dependents_count)


def compute_repayment_amount(
    due_capital: Decimal,
    remaining_seizable: Decimal,
    remaining_capital: Decimal | None = None,
) -> Decimal:
    """Montant de capital effectivement prélevé ce mois."""
    if due_capital <= 0 or remaining_seizable <= 0:
        return Decimal("0.00")
    amount = min(due_capital, remaining_seizable)
    if remaining_capital is not None:
        amount = min(amount, remaining_capital)
    return _money(amount)


def compute_interest_paid(
    due_capital: Decimal,
    due_interest: Decimal,
    capital_paid: Decimal,
) -> Decimal:
    """Intérêts prélevés, proportionnels au capital remboursé si partiel."""
    if capital_paid <= 0 or due_interest <= 0:
        return Decimal("0.00")
    if due_capital <= 0 or capital_paid >= due_capital:
        return due_interest
    ratio = capital_paid / due_capital
    return _money(due_interest * ratio)


def compute_installment_remaining(
    capital_part: Decimal,
    interest_part: Decimal,
    capital_paid: Decimal,
    interest_paid: Decimal,
) -> tuple[Decimal, Decimal]:
    """Reliquat capital et intérêts restants sur une échéance."""
    remaining_capital = _money(max(Decimal("0"), capital_part - capital_paid))
    remaining_interest = _money(max(Decimal("0"), interest_part - interest_paid))
    return remaining_capital, remaining_interest


def is_installment_collectible(
    inst_year: int,
    inst_month: int,
    payslip_year: int,
    payslip_month: int,
) -> bool:
    """True si la période bulletin permet de prélever cette échéance."""
    return (inst_year, inst_month) <= (payslip_year, payslip_month)


def is_installment_settled(
    capital_part: Decimal,
    interest_part: Decimal,
    capital_paid_total: Decimal,
    interest_paid_total: Decimal,
) -> bool:
    """True si l'échéance est entièrement soldée (cumuls)."""
    return (
        capital_paid_total >= capital_part and interest_paid_total >= interest_part
    )


def is_installment_fully_paid(
    due_capital: Decimal,
    due_interest: Decimal,
    capital_paid: Decimal,
    interest_paid: Decimal,
    remaining_after: Decimal,
) -> bool:
    """True si l'échéance du mois est entièrement soldée (prélèvement unique)."""
    if remaining_after <= 0:
        return True
    return capital_paid >= due_capital and interest_paid >= due_interest
