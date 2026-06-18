"""Schémas réponse — paramètres congés / RTT."""

from typing import List, Optional

from pydantic import BaseModel


class LeaveSettingsResponse(BaseModel):
    company_id: str
    cp_acquisition_days_per_month: float
    cp_counting_unit: str
    cp_reference_period_start_month: int
    cp_carryover_enabled: bool
    cp_carryover_max_days: Optional[float] = None
    cp_acquisition_rate_display: float
    cp_annual_days_display: float
    rtt_annual_days: Optional[float] = None
    rtt_use_calendar_formula: bool
    rtt_use_forfait_jours_formula: bool = False
    rtt_forfait_annual_days: int = 214
    rtt_forfait_cp_ouvres_deduction: float = 25.0
    rtt_forfait_cadres_only: bool = True
    rtt_annual_days_computed: float
    rtt_period_start_month: int
    rtt_period_end_month: int
    rtt_carryover_enabled: bool
    rtt_year_end_reminder_enabled: bool
    rtt_year_end_reminder_days_before: int
    configured: bool = False


class EmployeeLeaveAdjustmentResponse(BaseModel):
    employee_id: str
    year: int
    cp_n1_opening_balance: float
    cp_n_opening_balance: float
    rtt_opening_balance: float
    rtt_forfeited_at: Optional[str] = None
    rtt_forfeited_days: float = 0.0
    note: Optional[str] = None


class EmployeeLeaveBalanceOverviewItem(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    cp_n1_remaining: float
    cp_n_remaining: float
    cp_total_remaining: float
    cp_legal_days: float = 0.0
    cp_seniority_days: float = 0.0
    rtt_remaining: float
    adjustment_note: Optional[str] = None


class LeaveBalancesOverviewResponse(BaseModel):
    year: int
    employees: List[EmployeeLeaveBalanceOverviewItem]


class RttYearEndOverviewItem(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    rtt_remaining: float
    already_closed: bool
    closure_required: bool


class RttYearEndOverviewResponse(BaseModel):
    year: int
    reminder_active: bool
    employees: List[RttYearEndOverviewItem]


class LeaveAdjustmentImportResult(BaseModel):
    imported: int
    errors: List[str]


class RttYearEndCloseResult(BaseModel):
    closed_count: int
    total_days_forfeited: float
