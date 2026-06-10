"""Schémas de réponse prêts employeur."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoanInstallment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    loan_id: Optional[str] = None
    installment_number: int
    year: int
    month: int
    capital_part: float
    interest_part: float
    total_due: float
    status: Literal["pending", "paid", "skipped"] = "pending"
    payslip_id: Optional[str] = None


class LoanRepayment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    loan_id: str
    payslip_id: Optional[str] = None
    year: int
    month: int
    capital_amount: float
    interest_amount: float
    avantage_nature_amount: float
    remaining_after: float
    created_at: Optional[datetime] = None


class EmployeeLoan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    employee_id: str
    principal_amount: float
    annual_interest_rate: float
    start_date: date
    duration_months: int
    monthly_payment: float
    repayment_day: int
    reason: Optional[str] = None
    status: Literal[
        "draft", "active", "suspended", "repaid", "cancelled", "defaulted"
    ]
    remaining_capital: float
    requires_2062_declaration: bool = False
    declared_2062: bool = False
    contract_file_path: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    employee_name: Optional[str] = None


class AmortizationPreviewLine(BaseModel):
    installment_number: int
    year: int
    month: int
    capital_part: float
    interest_part: float
    total_due: float
    remaining_capital: float


class AmortizationPreview(BaseModel):
    monthly_payment: float
    requires_2062_declaration: bool
    schedule: List[AmortizationPreviewLine]


class EmployeeLoanOutstanding(BaseModel):
    employee_id: str
    total_remaining_capital: float
    active_loans_count: int
    outstanding_loans_count: int = 0
    loans: List[EmployeeLoan] = Field(default_factory=list)
