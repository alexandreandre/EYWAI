"""
Schémas Pydantic sortie API du module repos_compensateur.
"""

from __future__ import annotations

from pydantic import BaseModel


class CalculerCreditsResponse(BaseModel):
    """Réponse POST /api/repos-compensateur/calculer-credits."""

    company_id: str
    year: int
    month: int
    employees_processed: int
    credits_created: int


class ContingentSettingsResponse(BaseModel):
    company_id: str
    legal_cor_contingent_hours: float
    management_contingent_hours: float | None
    hours_per_rest_day: float
    include_structural_hours: bool
    pause_deduction_enabled: bool
    pause_hs_deduction_per_workday: float
    workdays_per_year_for_pause: int


class ContingentKPIsResponse(BaseModel):
    total_employees: int
    near_limit_count: int
    management_exceeded_count: int
    cor_exceeded_count: int


class ContingentOverviewRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    hire_date: str | None
    structural_hours: float
    paid_hours: float
    pause_deduction: float
    manual_adjustment: float
    rcr_hours: float
    consumed_hours: float
    total_for_ceiling: float
    margin_hours: float
    legal_cor_excess: float
    management_contingent: float
    legal_cor_contingent: float
    usage_percent: float
    status: str


class ContingentOverviewResponse(BaseModel):
    company_id: str
    year: int
    reference_date: str
    settings: ContingentSettingsResponse
    kpis: ContingentKPIsResponse
    employees: list[ContingentOverviewRow]


class ContingentMonthlyRowResponse(BaseModel):
    month: int
    paid_hours: float
    cumulative_consumed: float
    cumulative_total: float


class ContingentBreakdownResponse(BaseModel):
    structural_hours: float
    paid_hours: float
    pause_deduction: float
    manual_adjustment: float
    rcr_hours: float
    consumed_hours: float
    total_for_ceiling: float
    margin_hours: float
    legal_cor_excess: float
    management_contingent: float
    legal_cor_contingent: float
    usage_percent: float
    status: str


class EmployeeAdjustmentResponse(BaseModel):
    opening_balance_hours: float
    note: str | None = None


class ContingentEmployeeDetailResponse(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    hire_date: str | None
    year: int
    reference_date: str
    breakdown: ContingentBreakdownResponse
    monthly: list[ContingentMonthlyRowResponse]
    adjustment: EmployeeAdjustmentResponse
    settings: ContingentSettingsResponse
