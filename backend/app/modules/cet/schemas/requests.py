"""Schémas API CET."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class CetSettingsResponse(BaseModel):
    company_id: str
    cet_enabled: bool
    agreement_reference: Optional[str] = None
    hours_per_rest_day: float = 7.0
    request_deadline_day_of_month: Optional[int] = None
    validation_mode: Literal["auto", "rh"] = "rh"
    allow_deposit_hs: bool = True
    allow_deposit_cp: bool = False
    max_cp_days_per_year: Optional[float] = None
    max_account_balance_days: Optional[float] = None
    cp_unit: Literal["ouvres", "ouvrables"] = "ouvrables"
    ouvres_to_ouvrables_ratio: float = 1.2
    cp_debit_timing: Literal["on_validation", "on_payroll"] = "on_validation"
    hs_debit_timing: Literal["on_validation", "on_payroll"] = "on_payroll"


class CetSettingsUpdate(BaseModel):
    cet_enabled: Optional[bool] = None
    agreement_reference: Optional[str] = None
    hours_per_rest_day: Optional[float] = Field(None, gt=0)
    request_deadline_day_of_month: Optional[int] = Field(None, ge=1, le=28)
    validation_mode: Optional[Literal["auto", "rh"]] = None
    allow_deposit_hs: Optional[bool] = None
    allow_deposit_cp: Optional[bool] = None
    max_cp_days_per_year: Optional[float] = Field(None, ge=0)
    max_account_balance_days: Optional[float] = Field(None, ge=0)
    cp_unit: Optional[Literal["ouvres", "ouvrables"]] = None
    ouvres_to_ouvrables_ratio: Optional[float] = Field(None, gt=0)
    cp_debit_timing: Optional[Literal["on_validation", "on_payroll"]] = None
    hs_debit_timing: Optional[Literal["on_validation", "on_payroll"]] = None


class CetDepositRequest(BaseModel):
    hours: float = Field(..., gt=0)
    year: Optional[int] = Field(None, ge=2000, le=2100)
    month: Optional[int] = Field(None, ge=1, le=12)


class CetDepositCpRequest(BaseModel):
    days: float = Field(..., gt=0)
    year: Optional[int] = Field(None, ge=2000, le=2100)
    month: Optional[int] = Field(None, ge=1, le=12)


class CetWithdrawalRequest(BaseModel):
    hours: float = Field(..., gt=0)


class CetMovementValidateRequest(BaseModel):
    approved: bool


class CetPendingMovement(BaseModel):
    id: str
    movement_type: str
    hours: float = 0.0
    days: float = 0.0
    status: str
    year: int
    month: int
    created_at: Optional[str] = None


class CetSummaryResponse(BaseModel):
    employee_id: str
    company_id: str
    cet_enabled: bool
    eligible: bool
    allow_deposit_hs: bool = True
    allow_deposit_cp: bool = False
    cp_unit: Literal["ouvres", "ouvrables"] = "ouvrables"
    year: int
    month: int
    balance_hours: float
    overtime_hours_month: float
    spareable_hours: float
    rest_days_available: float
    hours_per_rest_day: float
    cp_transfer_used_days: float = 0.0
    cp_transfer_remaining_days: Optional[float] = None
    cp_balance_available: float = 0.0
    pending_movements: list[CetPendingMovement]
    settings: CetSettingsResponse
