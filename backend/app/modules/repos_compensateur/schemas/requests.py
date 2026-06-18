"""
Schémas Pydantic entrée API du module repos_compensateur.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContingentSettingsUpdate(BaseModel):
    legal_cor_contingent_hours: float | None = Field(None, ge=0, le=1000)
    management_contingent_hours: float | None = Field(None, ge=0, le=2000)
    hours_per_rest_day: float | None = Field(None, ge=0.5, le=24)
    include_structural_hours: bool | None = None
    pause_deduction_enabled: bool | None = None
    pause_hs_deduction_per_workday: float | None = Field(None, ge=0, le=24)
    workdays_per_year_for_pause: int | None = Field(None, ge=1, le=366)


class EmployeeAdjustmentUpdate(BaseModel):
    opening_balance_hours: float = Field(..., ge=-2000, le=2000)
    note: str | None = Field(None, max_length=500)
