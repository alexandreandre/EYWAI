"""Entités modulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

ModulationTier = Literal["high", "low", "neutral"]
FranchisePeriod = Literal["month", "pay_period"]
AccountCreditSource = Literal["overtime_only", "surplus_over_modulated"]
RecoveryDebitTiming = Literal["on_validation", "on_payroll"]
MovementType = Literal[
    "credit_hs",
    "debit_recovery",
    "debit_payout",
    "adjustment",
    "opening_balance",
]


@dataclass(frozen=True)
class ModulationSettings:
    enabled: bool = False
    reference_period_months: int = 12
    average_weekly_hours: float = 35.0
    weekly_high_hours: float = 37.0
    weekly_low_hours: float = 32.0
    high_weeks_per_cycle: int = 1
    low_weeks_per_cycle: int = 1
    cycle_start_week_iso: date | None = None
    pay_smoothed: bool = True
    weekly_cap_hours: float = 44.0
    theoretical_annual_hours: float | None = None
    hour_account_enabled: bool = False
    hs_franchise_hours_per_period: float | None = None
    hs_franchise_period: FranchisePeriod = "month"
    max_account_balance_hours: float | None = None
    account_credit_source: AccountCreditSource = "overtime_only"
    recovery_absence_enabled: bool = True
    recovery_debit_timing: RecoveryDebitTiming = "on_validation"


@dataclass(frozen=True)
class WeekScheduleTemplate:
    id: str
    company_id: str
    name: str
    weekly_hours: float
    day_configs: list[dict[str, Any]]
    modulation_tier: ModulationTier = "neutral"
    is_active: bool = True


@dataclass(frozen=True)
class EmployeeModulationCounter:
    employee_id: str
    year: int
    theoretical_hours: float
    actual_hours: float
    balance_hours: float
    account_balance_hours: float = 0.0
    period_credited_hours: float = 0.0
    period_paid_hours: float = 0.0


@dataclass(frozen=True)
class ModulationMovement:
    id: str
    company_id: str
    employee_id: str
    year: int
    month: int | None
    movement_type: MovementType
    hours: float
    status: str
    source: str
    reference_id: str | None = None
    metadata: dict[str, Any] | None = None
    note: str | None = None
