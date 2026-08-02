"""Schémas requêtes API médailles du travail."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

MedalLevel = Literal["argent", "vermeil", "or", "grand_or"]
SeniorityBasis = Literal["total_career", "company_only", "seniority_reference_date"]
AmountMode = Literal["fixed", "salary_months"]


class MedalTierInput(BaseModel):
    level: MedalLevel
    years: int = Field(ge=1, le=50)
    label: str
    amount_mode: AmountMode = "fixed"
    amount_value: float = Field(ge=0)


class WorkMedalSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    seniority_basis: Optional[SeniorityBasis] = None
    reminder_months_before: Optional[int] = Field(default=None, ge=0, le=24)
    tiers: Optional[list[MedalTierInput]] = None
    default_is_taxable: Optional[bool] = None
    default_is_socially_taxed: Optional[bool] = None


class WorkMedalApproveRequest(BaseModel):
    payroll_year: int = Field(ge=2000, le=2100)
    payroll_month: int = Field(ge=1, le=12)
    amount_override: Optional[float] = Field(default=None, ge=0)


class WorkMedalDismissRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)
