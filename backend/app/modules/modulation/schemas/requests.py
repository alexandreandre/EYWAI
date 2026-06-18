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


class WeekTemplateSchema(BaseModel):
    id: Optional[str] = None
    name: str
    weekly_hours: float = 35.0
    day_configs: list[dict[str, Any]] = Field(default_factory=list)
    modulation_tier: Literal["high", "low", "neutral"] = "neutral"
    is_active: bool = True


class ModulationOverviewRow(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    theoretical_hours: float = 0.0
    actual_hours: float = 0.0
    balance_hours: float = 0.0
