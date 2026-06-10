"""
Enrichissement bulletin : remboursements de prêts employeur sur le net à payer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.modules.employee_loans.domain.rules import (
    compute_interest_benefit_in_kind,
    compute_interest_paid,
    compute_loan_repayment_cap,
    compute_repayment_amount,
    is_installment_fully_paid,
)
from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_legal_interest_rate,
    get_loans_due_for_period,
    get_suspended_loans_with_pending_installment,
)
from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loan_repayments_repository,
    employee_loans_repository,
)


def process_suspended_loan_installments(
    employee_id: str,
    year: int,
    month: int,
) -> None:
    """Marque skipped les échéances pending des prêts suspendus pour ce mois."""
    suspended = get_suspended_loans_with_pending_installment(employee_id, year, month)
    for item in suspended:
        installment = item.get("installment") or {}
        inst_id = installment.get("id")
        if inst_id:
            try:
                employee_loan_installments_repository.update(
                    inst_id, {"status": "skipped"}
                )
            except Exception:
                pass


def enrich_payslip_loans(
    payslip_json_data: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
    payslip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Applique les retenues de remboursement de prêt sur le net à payer.
    Plafonnées à la fraction saisissable restante et au capital restant dû.
    """
    process_suspended_loan_installments(employee_id, year, month)

    net_a_payer = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
    seizable_remaining = compute_loan_repayment_cap(net_a_payer)

    loans_due = get_loans_due_for_period(employee_id, year, month)
    legal_rate = get_legal_interest_rate()

    total_capital = Decimal("0")
    total_interest = Decimal("0")
    total_an = Decimal("0")
    remboursements: List[Dict[str, Any]] = []

    for item in loans_due:
        loan = item
        installment = item.get("installment") or {}
        loan_id = loan["id"]

        if payslip_id:
            existing = employee_loan_repayments_repository.get_existing(
                loan_id, payslip_id
            )
            if existing:
                cap = Decimal(str(existing.get("capital_amount", 0)))
                total_capital += cap
                total_interest += Decimal(str(existing.get("interest_amount", 0)))
                total_an += Decimal(
                    str(existing.get("avantage_nature_amount", 0))
                )
                remboursements.append(
                    {
                        "loan_id": loan_id,
                        "montant_capital": float(cap),
                        "montant_interets": float(existing.get("interest_amount", 0)),
                        "reste_apres": float(existing.get("remaining_after", 0)),
                        "motif": loan.get("reason"),
                    }
                )
                continue

        due_capital = Decimal(str(installment.get("capital_part", 0)))
        due_interest = Decimal(str(installment.get("interest_part", 0)))
        remaining_capital = Decimal(str(loan.get("remaining_capital", 0)))

        capital_paid = compute_repayment_amount(
            due_capital, seizable_remaining, remaining_capital
        )
        interest_paid = compute_interest_paid(due_capital, due_interest, capital_paid)

        an_amount = compute_interest_benefit_in_kind(
            remaining_capital,
            legal_rate,
            Decimal(str(loan.get("annual_interest_rate", 0))),
        )
        if capital_paid < due_capital and due_capital > 0:
            an_amount = _money_proportional(an_amount, capital_paid, due_capital)

        seizable_remaining -= capital_paid + interest_paid
        total_capital += capital_paid
        total_interest += interest_paid
        total_an += an_amount

        remaining_after = _money(max(Decimal("0"), remaining_capital - capital_paid))
        remboursements.append(
            {
                "loan_id": loan_id,
                "montant_capital": float(capital_paid),
                "montant_interets": float(interest_paid),
                "reste_apres": float(remaining_after),
                "motif": loan.get("reason"),
            }
        )

        total_paid_this_month = capital_paid + interest_paid
        if total_paid_this_month > 0 and payslip_id:
            try:
                employee_loan_repayments_repository.create(
                    {
                        "loan_id": loan_id,
                        "payslip_id": payslip_id,
                        "year": year,
                        "month": month,
                        "capital_amount": float(capital_paid),
                        "interest_amount": float(interest_paid),
                        "avantage_nature_amount": float(an_amount),
                        "remaining_after": float(remaining_after),
                    }
                )
            except Exception:
                pass

            try:
                update_loan: Dict[str, Any] = {
                    "remaining_capital": float(remaining_after),
                }
                if remaining_after <= 0:
                    update_loan["status"] = "repaid"
                employee_loans_repository.update(loan_id, update_loan)
            except Exception:
                pass

            try:
                inst_id = installment.get("id")
                if inst_id and is_installment_fully_paid(
                    due_capital,
                    due_interest,
                    capital_paid,
                    interest_paid,
                    remaining_after,
                ):
                    employee_loan_installments_repository.update(
                        inst_id,
                        {"status": "paid", "payslip_id": payslip_id},
                    )
            except Exception:
                pass

    total_rembourse = total_capital + total_interest
    payslip_json_data["remboursements_prets"] = {
        "total_rembourse": float(total_rembourse),
        "total_capital": float(total_capital),
        "total_interets": float(total_interest),
        "avantage_nature_interets": float(total_an),
        "prets": remboursements,
    }

    if total_rembourse > 0:
        current_net = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
        payslip_json_data["net_a_payer"] = float(
            max(Decimal("0"), current_net - total_rembourse)
        )

    return payslip_json_data


def _money(value: Decimal) -> Decimal:
    from decimal import ROUND_HALF_UP

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_proportional(amount: Decimal, paid: Decimal, due: Decimal) -> Decimal:
    if due <= 0 or paid <= 0:
        return Decimal("0.00")
    if paid >= due:
        return amount
    return _money(amount * paid / due)
