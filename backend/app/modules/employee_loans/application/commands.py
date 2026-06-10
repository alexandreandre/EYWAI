"""Commandes prêts employeur."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from app.modules.employee_loans.domain.rules import (
    build_amortization_schedule,
    requires_2062,
)
from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loan_repayments_repository,
    employee_loans_repository,
)
from app.modules.employee_loans.schemas.responses import (
    AmortizationPreview,
    AmortizationPreviewLine,
    EmployeeLoan,
)

_ALLOWED_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    "draft": {"active", "cancelled"},
    "active": {"suspended", "repaid", "cancelled", "defaulted"},
    "suspended": {"active", "defaulted", "cancelled"},
    "repaid": set(),
    "cancelled": set(),
    "defaulted": set(),
}


def _get_employee_company_id(employee_id: str) -> str:
    from app.core.database import supabase

    r = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not r or not r.data:
        raise ValueError("Employé non trouvé.")
    return str(r.data["company_id"])


def _validate_status_transition(current: str, new: str) -> None:
    if current == new:
        return
    allowed = _ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ValueError(
            f"Transition de statut invalide : {current} → {new}."
        )


def _build_preview(
    principal: Decimal,
    annual_rate: Decimal,
    duration_months: int,
    start_date: date,
) -> AmortizationPreview:
    monthly_payment, lines = build_amortization_schedule(
        principal, annual_rate, duration_months, start_date
    )
    return AmortizationPreview(
        monthly_payment=float(monthly_payment),
        requires_2062_declaration=requires_2062(principal),
        schedule=[
            AmortizationPreviewLine(
                installment_number=line.installment_number,
                year=line.year,
                month=line.month,
                capital_part=float(line.capital_part),
                interest_part=float(line.interest_part),
                total_due=float(line.total_due),
                remaining_capital=float(line.remaining_capital),
            )
            for line in lines
        ],
    )


def create_loan(
    company_id: str,
    data: Any,
    created_by: Optional[str],
) -> EmployeeLoan:
    employee_company = _get_employee_company_id(data.employee_id)
    if employee_company != company_id:
        raise ValueError("L'employé n'appartient pas à l'entreprise active.")

    principal = Decimal(str(data.principal_amount))
    annual_rate = Decimal(str(data.annual_interest_rate))
    monthly_payment, schedule = build_amortization_schedule(
        principal,
        annual_rate,
        data.duration_months,
        data.start_date,
    )

    status = "active" if data.activate else "draft"
    remaining = principal if status == "active" else Decimal("0")

    loan_row = employee_loans_repository.create(
        {
            "company_id": company_id,
            "employee_id": data.employee_id,
            "principal_amount": float(principal),
            "annual_interest_rate": float(annual_rate),
            "start_date": data.start_date.isoformat(),
            "duration_months": data.duration_months,
            "monthly_payment": float(monthly_payment),
            "repayment_day": data.repayment_day,
            "reason": data.reason,
            "notes": data.notes,
            "status": status,
            "remaining_capital": float(remaining),
            "requires_2062_declaration": requires_2062(principal),
            "declared_2062": False,
            "created_by": created_by,
        }
    )

    installment_rows: List[Dict[str, Any]] = []
    for line in schedule:
        installment_rows.append(
            {
                "loan_id": loan_row["id"],
                "installment_number": line.installment_number,
                "year": line.year,
                "month": line.month,
                "capital_part": float(line.capital_part),
                "interest_part": float(line.interest_part),
                "total_due": float(line.total_due),
                "status": "pending",
            }
        )
    employee_loan_installments_repository.bulk_create(installment_rows)
    return EmployeeLoan.model_validate(loan_row)


def update_loan(loan_id: str, data: Any) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")

    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return EmployeeLoan.model_validate(loan)

    new_status = patch.get("status")
    if new_status is not None:
        _validate_status_transition(str(loan.get("status")), str(new_status))

    if new_status == "active" and loan.get("status") == "draft":
        patch["remaining_capital"] = loan.get("principal_amount")

    row = employee_loans_repository.update(loan_id, patch)
    if not row:
        raise ValueError("Prêt non trouvé.")
    return EmployeeLoan.model_validate(row)


def activate_loan(loan_id: str) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if loan.get("status") != "draft":
        raise ValueError("Seul un prêt brouillon peut être activé.")
    row = employee_loans_repository.update(
        loan_id,
        {
            "status": "active",
            "remaining_capital": loan.get("principal_amount"),
        },
    )
    if not row:
        raise ValueError("Prêt non trouvé.")
    return EmployeeLoan.model_validate(row)


def cancel_loan(loan_id: str) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if loan.get("status") in ("repaid", "cancelled"):
        raise ValueError("Ce prêt ne peut plus être annulé.")
    employee_loan_installments_repository.skip_pending_for_loan(loan_id)
    row = employee_loans_repository.update(
        loan_id, {"status": "cancelled", "remaining_capital": 0}
    )
    return EmployeeLoan.model_validate(row)


def mark_loan_defaulted(loan_id: str) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if loan.get("status") not in ("active", "suspended"):
        raise ValueError("Seul un prêt actif ou suspendu peut être mis en défaut.")
    employee_loan_installments_repository.skip_pending_for_loan(loan_id)
    row = employee_loans_repository.update(loan_id, {"status": "defaulted"})
    if not row:
        raise ValueError("Prêt non trouvé.")
    return EmployeeLoan.model_validate(row)


def record_early_repayment(loan_id: str, amount: float, repayment_date: date) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if loan.get("status") != "active":
        raise ValueError("Seul un prêt actif peut être remboursé par anticipation.")

    remaining = Decimal(str(loan.get("remaining_capital", 0)))
    payment = Decimal(str(amount))
    if payment <= 0 or payment > remaining:
        raise ValueError("Montant de remboursement invalide.")

    new_remaining = remaining - payment
    update: Dict[str, Any] = {
        "remaining_capital": float(max(Decimal("0"), new_remaining)),
        "notes": (loan.get("notes") or "")
        + f"\nRemboursement anticipé {payment}€ le {repayment_date.isoformat()}.",
    }
    if new_remaining <= 0:
        update["status"] = "repaid"
        update["remaining_capital"] = 0
        employee_loan_installments_repository.mark_pending_paid_for_loan(loan_id)

    row = employee_loans_repository.update(loan_id, update)

    employee_loan_repayments_repository.create(
        {
            "loan_id": loan_id,
            "payslip_id": None,
            "year": repayment_date.year,
            "month": repayment_date.month,
            "capital_amount": float(payment),
            "interest_amount": 0,
            "avantage_nature_amount": 0,
            "remaining_after": float(max(Decimal("0"), new_remaining)),
        }
    )

    return EmployeeLoan.model_validate(row)


def mark_declared_2062(loan_id: str) -> EmployeeLoan:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    row = employee_loans_repository.update(loan_id, {"declared_2062": True})
    return EmployeeLoan.model_validate(row)


def delete_loan(loan_id: str) -> None:
    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if loan.get("status") not in ("draft", "cancelled"):
        raise ValueError("Seuls les prêts brouillon ou annulés peuvent être supprimés.")
    employee_loans_repository.delete(loan_id)


def _fetch_contract_parties(company_id: str, employee_id: str) -> tuple[dict, dict]:
    from app.core.database import supabase

    company_res = (
        supabase.table("companies").select("*").eq("id", company_id).maybe_single().execute()
    )
    employee_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not company_res.data or not employee_res.data:
        raise LookupError("Données entreprise ou employé introuvables.")
    return company_res.data, employee_res.data


def generate_loan_contract(loan_id: str, company_id: str) -> dict:
    from app.modules.employee_loans.documents.loan_contract_generator import (
        generate_loan_contract_pdf,
        store_loan_contract,
    )

    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan:
        raise ValueError("Prêt non trouvé.")
    if str(loan.get("company_id")) != str(company_id):
        raise PermissionError("Accès refusé.")

    company_data, employee_data = _fetch_contract_parties(
        company_id, str(loan["employee_id"])
    )
    pdf_bytes = generate_loan_contract_pdf(loan_id, company_data, employee_data)
    path = store_loan_contract(loan_id, company_id, pdf_bytes)
    return {"path": path, "message": "Contrat généré."}
