"""
Enrichissement bulletin : remboursements de prêts employeur sur le net à payer.
Remboursement glissant : reprise de l'échéance non soldée mois après mois.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.modules.employee_loans.domain.rules import (
    compute_installment_remaining,
    compute_interest_benefit_in_kind,
    compute_interest_paid,
    compute_loan_repayment_cap,
    compute_repayment_amount,
    is_installment_settled,
)
from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_legal_interest_rate,
    get_suspended_loans_with_pending_installment,
    get_unsettled_installments_for_payroll,
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
    """Marque skipped les échéances pending/partial des prêts suspendus pour ce mois."""
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
    Reprend la plus ancienne échéance non soldée ; plafonné à la quotité saisissable.
    """
    process_suspended_loan_installments(employee_id, year, month)

    net_a_payer = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
    seizable_remaining = compute_loan_repayment_cap(net_a_payer)

    loans_due = get_unsettled_installments_for_payroll(employee_id, year, month)
    legal_rate = get_legal_interest_rate()

    total_capital = Decimal("0")
    total_interest = Decimal("0")
    total_an = Decimal("0")
    remboursements: List[Dict[str, Any]] = []

    for item in loans_due:
        loan = item
        installment = item.get("installment") or {}
        loan_id = loan["id"]
        inst_id = installment.get("id")

        if payslip_id:
            existing = employee_loan_repayments_repository.get_existing(
                loan_id, payslip_id
            )
            if existing:
                cap = Decimal(str(existing.get("capital_amount", 0)))
                intr = Decimal(str(existing.get("interest_amount", 0)))
                total_capital += cap
                total_interest += intr
                total_an += Decimal(
                    str(existing.get("avantage_nature_amount", 0))
                )
                remboursements.append(
                    _build_remboursement_entry(
                        loan, installment, cap, intr,
                        Decimal(str(existing.get("remaining_after", 0))),
                        existing.get("installment_id"),
                    )
                )
                continue

        if seizable_remaining <= 0:
            break

        capital_part = Decimal(str(installment.get("capital_part", 0)))
        interest_part = Decimal(str(installment.get("interest_part", 0)))
        capital_paid_so_far = Decimal(str(installment.get("capital_paid") or 0))
        interest_paid_so_far = Decimal(str(installment.get("interest_paid") or 0))
        remaining_capital = Decimal(str(loan.get("remaining_capital", 0)))

        due_capital, due_interest = compute_installment_remaining(
            capital_part,
            interest_part,
            capital_paid_so_far,
            interest_paid_so_far,
        )

        if due_capital <= 0 and due_interest <= 0:
            if inst_id:
                try:
                    employee_loan_installments_repository.update(
                        inst_id, {"status": "paid", "payslip_id": payslip_id}
                    )
                except Exception:
                    pass
            continue

        capital_paid_this = compute_repayment_amount(
            due_capital, seizable_remaining, remaining_capital
        )
        interest_paid_this = compute_interest_paid(
            due_capital, due_interest, capital_paid_this
        )

        an_amount = compute_interest_benefit_in_kind(
            remaining_capital,
            legal_rate,
            Decimal(str(loan.get("annual_interest_rate", 0))),
        )
        if capital_paid_this < due_capital and due_capital > 0:
            an_amount = _money_proportional(an_amount, capital_paid_this, due_capital)

        seizable_remaining -= capital_paid_this + interest_paid_this
        total_capital += capital_paid_this
        total_interest += interest_paid_this
        total_an += an_amount

        remaining_after = _money(
            max(Decimal("0"), remaining_capital - capital_paid_this)
        )
        new_capital_paid = capital_paid_so_far + capital_paid_this
        new_interest_paid = interest_paid_so_far + interest_paid_this

        reliquat_capital, reliquat_interest = compute_installment_remaining(
            capital_part,
            interest_part,
            new_capital_paid,
            new_interest_paid,
        )
        reliquat_apres = _money(reliquat_capital + reliquat_interest)

        remboursements.append(
            _build_remboursement_entry(
                loan,
                installment,
                capital_paid_this,
                interest_paid_this,
                remaining_after,
                inst_id,
                reliquat_apres=reliquat_apres,
            )
        )

        total_paid_this_month = capital_paid_this + interest_paid_this
        if total_paid_this_month > 0 and payslip_id:
            settled = is_installment_settled(
                capital_part,
                interest_part,
                new_capital_paid,
                new_interest_paid,
            ) or remaining_after <= 0
            inst_status = "paid" if settled else "partial"

            try:
                repayment_payload: Dict[str, Any] = {
                    "loan_id": loan_id,
                    "payslip_id": payslip_id,
                    "year": year,
                    "month": month,
                    "capital_amount": float(capital_paid_this),
                    "interest_amount": float(interest_paid_this),
                    "avantage_nature_amount": float(an_amount),
                    "remaining_after": float(remaining_after),
                }
                if inst_id:
                    repayment_payload["installment_id"] = inst_id
                employee_loan_repayments_repository.create(repayment_payload)
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

            if inst_id:
                try:
                    employee_loan_installments_repository.increment_paid(
                        inst_id,
                        float(capital_paid_this),
                        float(interest_paid_this),
                        inst_status,
                        payslip_id=payslip_id if settled else None,
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


def _build_remboursement_entry(
    loan: Dict[str, Any],
    installment: Dict[str, Any],
    capital: Decimal,
    interest: Decimal,
    remaining_after: Decimal,
    installment_id: Optional[str],
    reliquat_apres: Optional[Decimal] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "loan_id": loan["id"],
        "installment_id": installment_id,
        "installment_number": installment.get("installment_number"),
        "montant_capital": float(capital),
        "montant_interets": float(interest),
        "reste_apres": float(remaining_after),
        "motif": loan.get("reason"),
    }
    if reliquat_apres is not None:
        entry["reliquat_apres"] = float(reliquat_apres)
    return entry


def _money(value: Decimal) -> Decimal:
    from decimal import ROUND_HALF_UP

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_proportional(amount: Decimal, paid: Decimal, due: Decimal) -> Decimal:
    if due <= 0 or paid <= 0:
        return Decimal("0.00")
    if paid >= due:
        return amount
    return _money(amount * paid / due)
