"""Lectures prêts employeur."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.employee_loans.infrastructure.payroll_queries import (
    get_employee_outstanding_loans,
    get_legal_interest_rate,
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
    EmployeeLoanOutstanding,
    LoanInstallment,
    LoanRepayment,
)


def list_loans(
    company_id: str,
    *,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[EmployeeLoan]:
    rows = employee_loans_repository.list_(
        company_id, employee_id=employee_id, status=status
    )
    return [EmployeeLoan.model_validate(r) for r in rows]


def get_loan(loan_id: str) -> EmployeeLoan:
    row = employee_loans_repository.get_by_id(loan_id)
    if not row:
        raise ValueError("Prêt non trouvé.")
    return EmployeeLoan.model_validate(row)


def get_loan_schedule(loan_id: str) -> List[LoanInstallment]:
    rows = employee_loan_installments_repository.list_by_loan(loan_id)
    return [LoanInstallment.model_validate(r) for r in rows]


def get_loan_repayments(loan_id: str) -> List[LoanRepayment]:
    rows = employee_loan_repayments_repository.list_by_loan(loan_id)
    return [LoanRepayment.model_validate(r) for r in rows]


def get_employee_loans(employee_id: str, company_id: str) -> List[EmployeeLoan]:
    return list_loans(company_id, employee_id=employee_id)


def get_outstanding_for_employee(employee_id: str) -> EmployeeLoanOutstanding:
    data = get_employee_outstanding_loans(employee_id)
    loans = [EmployeeLoan.model_validate(l) for l in data.get("loans", [])]
    return EmployeeLoanOutstanding(
        employee_id=employee_id,
        total_remaining_capital=data["total_remaining_capital"],
        active_loans_count=data["active_loans_count"],
        loans=loans,
    )


def preview_amortization(payload: Any) -> AmortizationPreview:
    from decimal import Decimal

    from app.modules.employee_loans.application.commands import _build_preview

    return _build_preview(
        Decimal(str(payload.principal_amount)),
        Decimal(str(payload.annual_interest_rate)),
        payload.duration_months,
        payload.start_date,
    )


def get_legal_rate() -> float:
    return float(get_legal_interest_rate())


def get_contract_signed_url(loan_id: str) -> str:
    from app.modules.employee_loans.infrastructure.providers import employee_loan_storage

    loan = employee_loans_repository.get_by_id(loan_id)
    if not loan or not loan.get("contract_file_path"):
        raise ValueError("Contrat non généré.")
    return employee_loan_storage.create_signed_download_url(str(loan["contract_file_path"]))
