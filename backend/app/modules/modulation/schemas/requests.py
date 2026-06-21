"""Schémas modulation."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModulationSettingsResponse(BaseModel):
    company_id: str
    enabled: bool = False
    configured: bool = False
    reference_period_months: int = 12
    average_weekly_hours: float = 35.0
    weekly_high_hours: float = 37.0
    weekly_low_hours: float = 32.0
    high_weeks_per_cycle: int = 1
    low_weeks_per_cycle: int = 1
    cycle_start_week_iso: Optional[date] = None
    pay_smoothed: bool = True
    weekly_cap_hours: float = 44.0
    theoretical_annual_hours: Optional[float] = None
    hour_account_enabled: bool = False
    hs_franchise_hours_per_period: Optional[float] = None
    hs_franchise_period: Literal["month", "pay_period"] = "month"
    max_account_balance_hours: Optional[float] = None
    account_credit_source: Literal["overtime_only", "surplus_over_modulated"] = (
        "overtime_only"
    )
    recovery_absence_enabled: bool = True
    recovery_debit_timing: Literal["on_validation", "on_payroll"] = "on_validation"
    hs_routing_policy: Literal["pay_all", "account_all", "franchise", "manual"] = (
        "franchise"
    )


class ModulationSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    reference_period_months: Optional[int] = Field(None, ge=1, le=12)
    average_weekly_hours: Optional[float] = Field(None, gt=0, le=48)
    weekly_high_hours: Optional[float] = Field(None, gt=0, le=48)
    weekly_low_hours: Optional[float] = Field(None, gt=0, le=48)
    high_weeks_per_cycle: Optional[int] = Field(None, ge=0, le=52)
    low_weeks_per_cycle: Optional[int] = Field(None, ge=0, le=52)
    cycle_start_week_iso: Optional[date] = None
    pay_smoothed: Optional[bool] = None
    weekly_cap_hours: Optional[float] = Field(None, gt=0, le=48)
    theoretical_annual_hours: Optional[float] = Field(None, ge=0)
    hour_account_enabled: Optional[bool] = None
    hs_franchise_hours_per_period: Optional[float] = Field(None, ge=0, le=500)
    hs_franchise_period: Optional[Literal["month", "pay_period"]] = None
    max_account_balance_hours: Optional[float] = Field(None, ge=0, le=2000)
    account_credit_source: Optional[
        Literal["overtime_only", "surplus_over_modulated"]
    ] = None
    recovery_absence_enabled: Optional[bool] = None
    recovery_debit_timing: Optional[Literal["on_validation", "on_payroll"]] = None
    hs_routing_policy: Optional[
        Literal["pay_all", "account_all", "franchise", "manual"]
    ] = None


class WeekTemplateSchema(BaseModel):
    id: Optional[str] = None
    name: str
    weekly_hours: float = 35.0
    day_configs: list[dict[str, Any]] = Field(default_factory=list)
    modulation_tier: Literal["high", "low", "neutral"] = "neutral"
    is_active: bool = True
    team_id: Optional[str] = None
    description: Optional[str] = None


class WorkTimePeriodSchema(BaseModel):
    id: Optional[str] = None
    label: str
    start_date: date
    end_date: Optional[date] = None
    daily_reference_hours: Optional[float] = Field(None, gt=0, le=24)
    weekly_reference_hours: Optional[float] = Field(None, gt=0, le=48)
    affects_payroll: bool = True
    affects_planning: bool = False
    default_week_template_id: Optional[str] = None
    is_active: bool = True


class WorkTimePeriodUpdate(BaseModel):
    label: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    daily_reference_hours: Optional[float] = Field(None, gt=0, le=24)
    weekly_reference_hours: Optional[float] = Field(None, gt=0, le=48)
    affects_payroll: Optional[bool] = None
    affects_planning: Optional[bool] = None
    default_week_template_id: Optional[str] = None
    is_active: Optional[bool] = None


class OvertimeRoutingRow(BaseModel):
    employee_id: str
    employee_name: str
    total_hs_hours: float
    hours_to_pay: float
    hours_to_account: float
    status: str
    note: Optional[str] = None


class OvertimeRoutingDecisionUpdate(BaseModel):
    hours_to_pay: float = Field(..., ge=0)
    hours_to_account: float = Field(..., ge=0)
    note: Optional[str] = None
    submit_validated: bool = False


class ModulationOverviewRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    theoretical_hours: float = 0.0
    actual_hours: float = 0.0
    balance_hours: float = 0.0
    account_balance_hours: float = 0.0
    period_credited_hours: float = 0.0
    period_paid_hours: float = 0.0


class ModulationBalanceResponse(BaseModel):
    employee_id: str
    year: int
    account_balance_hours: float = 0.0
    acquired_hours: float = 0.0
    taken_hours: float = 0.0
    franchise_remaining_hours: float = 0.0


class ModulationMovementSchema(BaseModel):
    id: str
    employee_id: str
    year: int
    month: Optional[int] = None
    movement_type: str
    hours: float
    status: str
    source: str
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    created_at: Optional[str] = None


class OpeningBalanceCreate(BaseModel):
    hours: float = Field(..., gt=0, le=2000)
    note: Optional[str] = None


class ManualAdjustmentCreate(BaseModel):
    employee_id: str
    hours: float = Field(..., ge=-2000, le=2000)
    note: Optional[str] = None
    year: Optional[int] = None
