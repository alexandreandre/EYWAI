"""Entités modulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

ModulationTier = Literal["high", "low", "neutral"]


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
