"""Schémas de requête prêts employeur."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeLoanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str
    principal_amount: float = Field(gt=0)
    annual_interest_rate: float = Field(default=0, ge=0, le=1)
    start_date: date
    duration_months: int = Field(ge=1, le=360)
    repayment_day: int = Field(default=1, ge=1, le=28)
    reason: Optional[str] = None
    notes: Optional[str] = None
    activate: bool = True


class EmployeeLoanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[
        Literal["draft", "active", "suspended", "repaid", "cancelled", "defaulted"]
    ] = None
    declared_2062: Optional[bool] = None
    notes: Optional[str] = None


class AmortizationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_amount: float = Field(gt=0)
    annual_interest_rate: float = Field(default=0, ge=0, le=1)
    start_date: date
    duration_months: int = Field(ge=1, le=360)


class EarlyRepaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    repayment_date: date
