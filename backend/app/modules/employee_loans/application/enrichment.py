"""
Enrichissement bulletin : remboursements de prêts employeur sur le net à payer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.modules.employee_loans.domain.rules import (
    compute_interest_benefit_in_kind,
    compute_loan_repayment_cap,
    compute_repayment_amount,
)
from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_legal_interest_rate,
    get_loans_due_for_period,
)
from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loan_repayments_repository,
    employee_loans_repository,
)


def enrich_payslip_loans(
    payslip_json_data: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
    payslip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Applique les retenues de remboursement de prêt sur le net à payer.
    Plafonnées à la fraction saisissable restante.
    """
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

        an_amount = compute_interest_benefit_in_kind(
            remaining_capital,
            legal_rate,
            Decimal(str(loan.get("annual_interest_rate", 0))),
        )

        capital_paid = compute_repayment_amount(due_capital, seizable_remaining)
        seizable_remaining -= capital_paid
        total_capital += capital_paid
        total_interest += due_interest
        total_an += an_amount

        remaining_after = remaining_capital - capital_paid
        remboursements.append(
            {
                "loan_id": loan_id,
                "montant_capital": float(capital_paid),
                "montant_interets": float(due_interest),
                "reste_apres": float(max(Decimal("0"), remaining_after)),
                "motif": loan.get("reason"),
            }
        )

        if capital_paid > 0 and payslip_id:
            try:
                employee_loan_repayments_repository.create(
                    {
                        "loan_id": loan_id,
                        "payslip_id": payslip_id,
                        "year": year,
                        "month": month,
                        "capital_amount": float(capital_paid),
                        "interest_amount": float(due_interest),
                        "avantage_nature_amount": float(an_amount),
                        "remaining_after": float(max(Decimal("0"), remaining_after)),
                    }
                )
            except Exception:
                pass

            try:
                update_loan: Dict[str, Any] = {
                    "remaining_capital": float(max(Decimal("0"), remaining_after)),
                }
                if remaining_after <= 0:
                    update_loan["status"] = "repaid"
                employee_loans_repository.update(loan_id, update_loan)
            except Exception:
                pass

            try:
                inst_id = installment.get("id")
                if inst_id:
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
