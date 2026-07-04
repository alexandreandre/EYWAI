"""Entités domaine — comptabilisation pointages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SlotDetection = Literal["shift_code", "nearest_entry", "planning_first"]
OvertimeReason = Literal["early_entry", "late_exit", "daily_excess"]
ReviewStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class PunchAccountingSettings:
    enabled: bool = False
    tolerance_minutes: int = 30
    default_break_deduct_minutes: int = 45
    use_last_nonzero_exit: bool = True
    slot_detection: SlotDetection = "shift_code"
    within_tolerance_pay_theoretical: bool = True
    require_manager_validation_for_overtime: bool = True


@dataclass(frozen=True)
class PunchShiftSlot:
    id: str | None = None
    code: str | None = None
    label: str = ""
    entry_minutes: int = 0
    exit_minutes: int = 0
    theoretical_gross_minutes: int = 465
    break_deduct_minutes: int = 45
    paid_break_minutes: int = 0
    paid_lunch_break: bool = False
    sort_order: int = 0


@dataclass(frozen=True)
class PlannedShiftBreak:
    """Pause payée et créneau planifié (shift_types / calendrier prévu)."""

    paid_break_minutes: int = 0
    unpaid_break_minutes: int | None = None
    planned_entry_minutes: int | None = None
    slot_code: str | None = None


@dataclass(frozen=True)
class PunchDayInput:
    entry_minutes: int | None = None
    exit_minutes: int | None = None
    shift_code: str | None = None
    planned_shift: PlannedShiftBreak | None = None


@dataclass(frozen=True)
class PunchDayResult:
    accounted_hours: float = 0.0
    theoretical_net_hours: float = 0.0
    pointed_net_hours: float = 0.0
    overtime_hours: float = 0.0
    overtime_reason: OvertimeReason | None = None
    needs_review: bool = False
    alerts: tuple[str, ...] = field(default_factory=tuple)
    applied_slot_id: str | None = None
    is_absent: bool = False


THREE_DAILY_SLOTS_PRESET: tuple[dict, ...] = (
    {
        "code": "A",
        "label": "Matin 8h – 15h45",
        "entry_time": "08:00",
        "exit_time": "15:45",
        "theoretical_gross_minutes": 465,
        "break_deduct_minutes": 45,
        "paid_lunch_break": False,
        "sort_order": 0,
    },
    {
        "code": "B",
        "label": "Équipe matin 4h45 – 12h",
        "entry_time": "04:45",
        "exit_time": "12:00",
        "theoretical_gross_minutes": 435,
        "break_deduct_minutes": 45,
        "paid_lunch_break": False,
        "sort_order": 1,
    },
    {
        "code": "B",
        "label": "Équipe après-midi 12h – 19h15",
        "entry_time": "12:00",
        "exit_time": "19:15",
        "theoretical_gross_minutes": 435,
        "break_deduct_minutes": 45,
        "paid_lunch_break": False,
        "sort_order": 2,
    },
)

EQUIPE_PAID_LUNCH_SLOTS_PRESET: tuple[dict, ...] = (
    {
        "code": "B",
        "label": "Équipe matin 4h45 – 12h (pause déjeuner payée)",
        "entry_time": "04:45",
        "exit_time": "12:00",
        "theoretical_gross_minutes": 435,
        "break_deduct_minutes": 15,
        "paid_lunch_break": True,
        "sort_order": 1,
    },
    {
        "code": "B",
        "label": "Équipe après-midi 12h – 19h15 (pause déjeuner payée)",
        "entry_time": "12:00",
        "exit_time": "19:15",
        "theoretical_gross_minutes": 435,
        "break_deduct_minutes": 15,
        "paid_lunch_break": True,
        "sort_order": 2,
    },
)

INDUSTRIAL_3X8_BREAKS_PRESET: tuple[dict, ...] = (
    {
        "code": "MATIN",
        "label": "Matin 04h00 – 12h00 (2×10 payées + repas 30)",
        "entry_time": "04:00",
        "exit_time": "12:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 30,
        "paid_break_minutes": 20,
        "paid_lunch_break": False,
        "sort_order": 0,
    },
    {
        "code": "APREM",
        "label": "Après-midi 12h00 – 20h00 (2×10 payées + repas 30)",
        "entry_time": "12:00",
        "exit_time": "20:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 30,
        "paid_break_minutes": 20,
        "paid_lunch_break": False,
        "sort_order": 1,
    },
    {
        "code": "JOUR",
        "label": "Journée 06h00 – 14h00 (2×10 payées + repas 30)",
        "entry_time": "06:00",
        "exit_time": "14:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 30,
        "paid_break_minutes": 20,
        "paid_lunch_break": False,
        "sort_order": 2,
    },
    {
        "code": "JOURNEE",
        "label": "Journée 08h00 – 16h00 (2×10 payées + repas 30)",
        "entry_time": "08:00",
        "exit_time": "16:00",
        "theoretical_gross_minutes": 480,
        "break_deduct_minutes": 30,
        "paid_break_minutes": 20,
        "paid_lunch_break": False,
        "sort_order": 3,
    },
)
