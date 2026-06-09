"""Schémas réponses API médailles du travail."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MedalLevel = Literal["argent", "vermeil", "or", "grand_or"]
SeniorityBasis = Literal["total_career", "company_only"]
AmountMode = Literal["fixed", "salary_months"]
CaseStatus = Literal[
    "upcoming",
    "awaiting_employee",
    "awaiting_rh",
    "approved",
    "paid",
    "dismissed",
]


class MedalTier(BaseModel):
    level: MedalLevel
    years: int
    label: str
    amount_mode: AmountMode = "fixed"
    amount_value: float = 0


class WorkMedalSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    enabled: bool = False
    seniority_basis: SeniorityBasis = "total_career"
    reminder_months_before: int = 6
    tiers: list[MedalTier] = Field(default_factory=list)
    default_is_taxable: bool = True
    default_is_socially_taxed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkMedalCase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    employee_id: str
    medal_level: MedalLevel
    milestone_years: int
    eligible_date: date
    status: CaseStatus
    amount_computed: Optional[float] = None
    payroll_year: Optional[int] = None
    payroll_month: Optional[int] = None
    monthly_input_id: Optional[str] = None
    employee_confirmed_at: Optional[datetime] = None
    rh_validated_at: Optional[datetime] = None
    rh_validated_by: Optional[str] = None
    dismissed_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None


class WorkMedalSummary(BaseModel):
    awaiting_rh: int = 0
    awaiting_employee: int = 0
    upcoming: int = 0
    total_actionable: int = 0


class WorkMedalScanResult(BaseModel):
    created: int = 0
    updated: int = 0
    notifications_sent: int = 0
