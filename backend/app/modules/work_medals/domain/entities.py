"""Entités domaine médailles du travail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Optional

MedalLevel = Literal["argent", "vermeil", "or", "grand_or"]
SeniorityBasis = Literal["total_career", "company_only", "seniority_reference_date"]
AmountMode = Literal["fixed", "salary_months"]
CaseStatus = Literal[
    "upcoming",
    "awaiting_employee",
    "awaiting_rh",
    "approved",
    "paid",
    "dismissed",
]


@dataclass(frozen=True)
class MedalTier:
    level: MedalLevel
    years: int
    label: str
    amount_mode: AmountMode
    amount_value: float


@dataclass
class WorkMedalSettings:
    company_id: str
    enabled: bool
    seniority_basis: SeniorityBasis
    reminder_months_before: int
    tiers: list[MedalTier]
    default_is_taxable: bool
    default_is_socially_taxed: bool
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class WorkMedalCase:
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


def tier_from_dict(raw: dict[str, Any]) -> MedalTier:
    return MedalTier(
        level=raw["level"],
        years=int(raw["years"]),
        label=str(raw.get("label") or raw["level"]),
        amount_mode=raw.get("amount_mode", "fixed"),
        amount_value=float(raw.get("amount_value", 0)),
    )
