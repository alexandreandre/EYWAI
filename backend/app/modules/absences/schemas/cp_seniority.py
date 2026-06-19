"""Schémas CP ancienneté."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CpSeniorityTierSchema(BaseModel):
    category: Literal["ouvrier_etam", "cadre", "forfait", "all"]
    min_years: float = Field(..., ge=0)
    days: float = Field(..., ge=0)
    min_age: Optional[float] = Field(None, ge=0, le=120)
    max_years: Optional[float] = Field(None, ge=0)


class CpSeniorityRulesSchema(BaseModel):
    mode: Literal["tier_total", "cumulative_rules"] = "tier_total"
    tiers: list[CpSeniorityTierSchema] = Field(default_factory=list)


class CpSenioritySettingsResponse(BaseModel):
    company_id: str
    enabled: bool = False
    configured: bool = False
    preset: Literal[
        "plasturgie_idcc_0292",
        "lewis_agreement",
        "metallurgie_idcc_3248",
        "custom",
    ] = "plasturgie_idcc_0292"
    seniority_reference: Literal["cp_period_end"] = "cp_period_end"
    seniority_basis: Literal[
        "company_only", "include_prior_service", "seniority_reference_date"
    ] = "company_only"
    counting_unit: Literal["ouvrable", "ouvre"] = "ouvrable"
    rules: CpSeniorityRulesSchema
    forfait_annual_days_default: float = 216.0
    forfait_reduction_enabled: bool = True
    company_agreement_overrides: bool = False
    recommended_preset: Optional[str] = None
    rules_source: Optional[str] = None


class CpSenioritySettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    preset: Optional[
        Literal[
            "plasturgie_idcc_0292",
            "lewis_agreement",
            "metallurgie_idcc_3248",
            "custom",
        ]
    ] = None
    seniority_reference: Optional[Literal["cp_period_end"]] = None
    seniority_basis: Optional[
        Literal[
            "company_only", "include_prior_service", "seniority_reference_date"
        ]
    ] = None
    counting_unit: Optional[Literal["ouvrable", "ouvre"]] = None
    rules: Optional[CpSeniorityRulesSchema] = None
    forfait_annual_days_default: Optional[float] = Field(None, gt=0)
    forfait_reduction_enabled: Optional[bool] = None
    company_agreement_overrides: Optional[bool] = None


class CpSeniorityPreviewRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    statut: Optional[str] = None
    category: Optional[str] = None
    seniority_years_at_ref: float = 0.0
    days_granted: float = 0.0
    days_before_prorata: float = 0.0
    prorata_applied: bool = False
    forfait_days_reduction: float = 0.0
    forfait_annual_days_adjusted: Optional[float] = None
    reference_date: str
    tier_matched: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)
    status: str = "computed"


class CpSeniorityGrantOverride(BaseModel):
    grant_year: int = Field(..., ge=2000, le=2100)
    days_granted: float = Field(..., ge=0)
    note: Optional[str] = None


class CpSeniorityValidateResult(BaseModel):
    grant_year: int
    validated_count: int
    status: str
