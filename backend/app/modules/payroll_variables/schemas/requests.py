"""Schémas variables paie."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PayrollVariableRuleSchema(BaseModel):
    id: Optional[str] = None
    code: str
    label: str
    enabled: bool = True
    rule_type: Literal[
        "fixed_monthly",
        "per_astreinte_week",
        "per_shift_type",
        "per_modulation_payout",
        "per_night_hour",
        "per_astreinte_weekend_km",
        "per_astreinte_week_tiered",
        "per_astreinte_weekend_majoration",
        "per_week_without_absence",
    ]
    bonus_type_id: Optional[str] = None
    amount: Optional[float] = None
    rate: Optional[float] = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    generation_mode: Literal["auto", "suggest"] = "auto"
    sort_order: int = 0


class SpecialPayrollDaySchema(BaseModel):
    id: Optional[str] = None
    day_date: str
    kind: Literal["bridge", "christmas_week"]
    label: Optional[str] = None


class AstreintePresetResponse(BaseModel):
    created_bonus_types: list[str]
    created_rules: list[str]
    skipped_existing: int


class PayrollVariablePreviewItem(BaseModel):
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    rule_code: Optional[str] = None
    rule_label: Optional[str] = None
    amount: float
    quantity: float = 1.0
    details: Optional[dict[str, Any]] = None


class PayrollVariableGenerateResponse(BaseModel):
    company_id: str
    year: int
    month: int
    dry_run: bool
    preview: list[PayrollVariablePreviewItem]
    written_count: int
