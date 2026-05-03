"""Schémas de réponse Pydantic v2 — module Planning."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ShiftTypeResponse(BaseModel):
    id: str
    code: str
    label: str
    color: str
    default_start: Optional[str] = None
    default_end: Optional[str] = None


class ShiftResponse(BaseModel):
    id: str
    company_id: str
    employee_id: str
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None
    shift_type: Optional[ShiftTypeResponse] = None
    transverse_category: Optional[str] = None
    shift_date: date
    start_time: str
    end_time: str
    post: Optional[str] = None
    location: Optional[str] = None
    comment_employee: Optional[str] = None
    is_locked: bool
    source: str
    created_at: str
    is_replacement: Optional[bool] = None
    replacing_employee_id: Optional[str] = None
    replacement_reason: Optional[str] = None
    original_employee_id: Optional[str] = None
    replacing_employee_name: Optional[str] = None
    original_employee_name: Optional[str] = None


class ShiftResponseRH(ShiftResponse):
    comment_internal: Optional[str] = None


class EmployeeHoursResponse(BaseModel):
    """Heures planifiées vs contrat (duree_hebdomadaire en base → contract_minutes)."""

    employee_id: str
    total_minutes: int
    contract_minutes: int
    delta: int


class WeekPlanningResponse(BaseModel):
    week_start: date
    week_end: date
    status: str
    payroll_transmitted: bool
    team_view_enabled: bool
    shifts: List[ShiftResponse]
    employee_hours: List[EmployeeHoursResponse]


class WeekStatusResponse(BaseModel):
    week_start: date
    status: str
    locked_at: Optional[str] = None
    payroll_transmitted: bool
    team_view_enabled: bool


class LockHistoryResponse(BaseModel):
    id: str
    action: str
    target_date: Optional[str] = None
    target_week_start: Optional[str] = None
    performed_by: Optional[str] = None
    reason: Optional[str] = None
    shifts_count: Optional[int] = None
    total_hours: Optional[float] = None
    created_at: str


class DuplicationResultResponse(BaseModel):
    shifts_created: int
    shifts_skipped: int
    conflicts: List[Dict[str, Any]]


class CollectiveAgreementResponse(BaseModel):
    id: str
    code: str
    label: str
    idcc: Optional[str] = None


class CompanyPlanningSettingsResponse(BaseModel):
    collective_agreement_id: Optional[str] = None
    collective_agreement: Optional[CollectiveAgreementResponse] = None
    team_view_default: bool
