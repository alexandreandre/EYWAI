"""Schémas fractionnement CP."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class FractionnementSettingsResponse(BaseModel):
    company_id: str
    fractionnement_enabled: bool
    cp_unit: Literal["ouvres", "ouvrables"] = "ouvres"
    ouvres_to_ouvrables_ratio: float = 1.2
    fifth_week_deduction_ouvres: float = 5.0
    calculation_method: Literal["mbc", "manual", "legal"] = "legal"
    exclude_forfait_jours: bool = True


class FractionnementSettingsUpdate(BaseModel):
    fractionnement_enabled: Optional[bool] = None
    cp_unit: Optional[Literal["ouvres", "ouvrables"]] = None
    ouvres_to_ouvrables_ratio: Optional[float] = Field(None, gt=0)
    fifth_week_deduction_ouvres: Optional[float] = Field(None, ge=0)
    calculation_method: Optional[Literal["mbc", "manual", "legal"]] = None
    exclude_forfait_jours: Optional[bool] = None


class FractionnementInputUpdate(BaseModel):
    grant_year: int = Field(..., ge=2000, le=2100)
    cp_reported_june_ouvres: float = Field(0, ge=0)
    cp_seniority_deduction_ouvres: float = Field(0, ge=0)
    report_june_manual_override: bool = True
    seniority_manual_override: bool = True
    manual_solde_ouvrables: Optional[float] = Field(None, ge=0)


class FractionnementPreviewRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    grant_year: int
    solde_cp_n1_ouvres: float
    cp_reported_june_ouvres: float
    cp_seniority_deduction_ouvres: float = 0.0
    auto_report_june_ouvres: Optional[float] = None
    auto_seniority_deduction_ouvres: Optional[float] = None
    report_june_manual_override: bool = False
    seniority_manual_override: bool = False
    prefill_source: Optional[dict[str, str]] = None
    manual_solde_ouvrables: float = 0.0
    solde_ouvres: float
    solde_ouvrables: float
    days_granted: int
    calculation_method: str = "legal"
    status: str = "computed"


class FractionnementValidateResult(BaseModel):
    grant_year: int
    validated_count: int
    status: str


class LeaveCampaignDashboard(BaseModel):
    grant_year: int
    phase: str
    today: str
    cp_seniority: dict[str, Any]
    fractionnement: dict[str, Any]
    alerts: list[dict[str, str]]
