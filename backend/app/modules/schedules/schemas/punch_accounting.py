"""Schémas API comptabilisation pointages."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SlotDetection = Literal["shift_code", "nearest_entry", "planning_first"]
ReviewStatus = Literal["pending", "approved", "rejected"]
OvertimeReason = Literal["early_entry", "late_exit", "daily_excess"]


class PunchAccountingSettingsResponse(BaseModel):
    configured: bool = False
    enabled: bool = False
    tolerance_minutes: int = 30
    default_break_deduct_minutes: int = 45
    use_last_nonzero_exit: bool = True
    slot_detection: SlotDetection = "shift_code"
    within_tolerance_pay_theoretical: bool = True
    require_manager_validation_for_overtime: bool = True


class PunchAccountingSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    tolerance_minutes: Optional[int] = Field(None, ge=0, le=120)
    default_break_deduct_minutes: Optional[int] = Field(None, ge=0, le=180)
    use_last_nonzero_exit: Optional[bool] = None
    slot_detection: Optional[SlotDetection] = None
    within_tolerance_pay_theoretical: Optional[bool] = None
    require_manager_validation_for_overtime: Optional[bool] = None


class PunchShiftSlotResponse(BaseModel):
    id: str
    code: Optional[str] = None
    label: str = ""
    entry_time: str
    exit_time: str
    theoretical_gross_minutes: int = 465
    break_deduct_minutes: int = 45
    paid_lunch_break: bool = False
    sort_order: int = 0


class PunchShiftSlotCreate(BaseModel):
    code: Optional[str] = None
    label: str = ""
    entry_time: str
    exit_time: str
    theoretical_gross_minutes: int = Field(465, ge=1, le=960)
    break_deduct_minutes: int = Field(45, ge=0, le=180)
    paid_lunch_break: bool = False
    sort_order: int = 0


class PunchShiftSlotUpdate(BaseModel):
    code: Optional[str] = None
    label: Optional[str] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    theoretical_gross_minutes: Optional[int] = Field(None, ge=1, le=960)
    break_deduct_minutes: Optional[int] = Field(None, ge=0, le=180)
    paid_lunch_break: Optional[bool] = None
    sort_order: Optional[int] = None


class PunchOvertimeReviewResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: Optional[str] = None
    work_date: str
    overtime_hours: float
    reason: OvertimeReason
    raw_entry_time: Optional[str] = None
    raw_exit_time: Optional[str] = None
    applied_slot_id: Optional[str] = None
    status: ReviewStatus
    review_note: Optional[str] = None


class PunchOvertimeReviewUpdate(BaseModel):
    status: ReviewStatus
    review_note: Optional[str] = None
