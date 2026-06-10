"""API prêts employeur."""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.employee_loans.api import access
from app.modules.employee_loans.application import commands, queries
from app.modules.employee_loans.schemas.requests import (
    AmortizationPreviewRequest,
    EarlyRepaymentRequest,
    EmployeeLoanCreate,
    EmployeeLoanUpdate,
)
from app.modules.employee_loans.schemas.responses import (
    AmortizationPreview,
    EmployeeLoan,
    EmployeeLoanOutstanding,
    LoanInstallment,
    LoanRepayment,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/employee-loans", tags=["EmployeeLoans"])


@router.post("/preview", response_model=AmortizationPreview)
def preview_amortization_route(
    body: AmortizationPreviewRequest,
    current_user: User = Depends(get_current_user),
) -> AmortizationPreview:
    access.require_rh_or_admin(current_user)
    try:
        return queries.preview_amortization(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/", response_model=EmployeeLoan, status_code=201)
def create_loan_route(
    body: EmployeeLoanCreate,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    company_id = access.require_rh_or_admin(current_user)
    try:
        return commands.create_loan(company_id, body, str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=List[EmployeeLoan])
def list_loans_route(
    employee_id: Optional[str] = Query(None),
    status: Optional[
        Literal["draft", "active", "suspended", "repaid", "cancelled", "defaulted"]
    ] = Query(None),
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLoan]:
    company_id = access.require_rh_or_admin(current_user)
    return queries.list_loans(company_id, employee_id=employee_id, status=status)


@router.get("/employees/me/loans", response_model=List[EmployeeLoan])
def get_my_loans_route(
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLoan]:
    employee_id = access.resolve_my_employee_id(current_user)
    company_id = access.require_company_id(current_user)
    return queries.get_employee_loans(employee_id, company_id)


@router.get("/employees/{employee_id}/loans", response_model=List[EmployeeLoan])
def get_employee_loans_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> List[EmployeeLoan]:
    company_id = access.require_rh_or_admin(current_user)
    return queries.get_employee_loans(employee_id, company_id)


@router.get(
    "/employees/{employee_id}/outstanding",
    response_model=EmployeeLoanOutstanding,
)
def get_employee_outstanding_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoanOutstanding:
    access.require_rh_or_admin(current_user)
    return queries.get_outstanding_for_employee(employee_id)


@router.get("/{loan_id}", response_model=EmployeeLoan)
def get_loan_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    return access.require_loan_access(current_user, loan_id)


@router.patch("/{loan_id}", response_model=EmployeeLoan)
def update_loan_route(
    loan_id: str,
    body: EmployeeLoanUpdate,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.update_loan(loan_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{loan_id}", status_code=204)
def delete_loan_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    access.require_rh_or_admin(current_user)
    try:
        commands.delete_loan(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{loan_id}/cancel", response_model=EmployeeLoan)
def cancel_loan_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.cancel_loan(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{loan_id}/activate", response_model=EmployeeLoan)
def activate_loan_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.activate_loan(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{loan_id}/default", response_model=EmployeeLoan)
def mark_defaulted_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.mark_loan_defaulted(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{loan_id}/early-repayment", response_model=EmployeeLoan)
def early_repayment_route(
    loan_id: str,
    body: EarlyRepaymentRequest,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.record_early_repayment(
            loan_id, body.amount, body.repayment_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{loan_id}/declared-2062", response_model=EmployeeLoan)
def mark_2062_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeLoan:
    access.require_rh_or_admin(current_user)
    try:
        return commands.mark_declared_2062(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{loan_id}/schedule", response_model=List[LoanInstallment])
def get_schedule_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> List[LoanInstallment]:
    access.require_loan_access(current_user, loan_id)
    return queries.get_loan_schedule(loan_id)


@router.get("/{loan_id}/repayments", response_model=List[LoanRepayment])
def get_repayments_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
) -> List[LoanRepayment]:
    access.require_loan_access(current_user, loan_id)
    return queries.get_loan_repayments(loan_id)


@router.post("/{loan_id}/contract")
def generate_contract_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = access.require_rh_or_admin(current_user)
    try:
        return commands.generate_loan_contract(loan_id, company_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{loan_id}/contract-url")
def get_contract_url_route(
    loan_id: str,
    current_user: User = Depends(get_current_user),
):
    access.require_loan_access(current_user, loan_id)
    try:
        url = queries.get_contract_signed_url(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"url": url}
