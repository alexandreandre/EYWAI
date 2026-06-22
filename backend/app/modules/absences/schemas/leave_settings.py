"""Schémas API — paramètres congés / RTT."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


CpCountingUnit = Literal["ouvrable", "ouvre"]


class LeaveSettingsUpdate(BaseModel):
    cp_acquisition_days_per_month: Optional[float] = Field(None, ge=0, le=10)
    cp_counting_unit: Optional[CpCountingUnit] = None
    cp_reference_period_start_month: Optional[int] = Field(None, ge=1, le=12)
    cp_carryover_enabled: Optional[bool] = None
    cp_carryover_max_days: Optional[float] = Field(None, ge=0, le=60)
    rtt_annual_days: Optional[float] = Field(None, ge=0, le=40)
    rtt_use_calendar_formula: Optional[bool] = None
    rtt_use_forfait_jours_formula: Optional[bool] = None
    rtt_forfait_annual_days: Optional[int] = Field(None, ge=180, le=250)
    rtt_forfait_cp_ouvres_deduction: Optional[float] = Field(None, ge=0, le=30)
    rtt_forfait_cadres_only: Optional[bool] = None
    rtt_period_start_month: Optional[int] = Field(None, ge=1, le=12)
    rtt_period_end_month: Optional[int] = Field(None, ge=1, le=12)
    rtt_carryover_enabled: Optional[bool] = None
    rtt_year_end_reminder_enabled: Optional[bool] = None
    rtt_year_end_reminder_days_before: Optional[int] = Field(None, ge=1, le=60)


class EmployeeLeaveAdjustmentUpdate(BaseModel):
    cp_n1_opening_balance: Optional[float] = Field(None, ge=-100, le=100)
    cp_n_opening_balance: Optional[float] = Field(None, ge=-100, le=100)
    rtt_opening_balance: Optional[float] = Field(None, ge=-100, le=100)
    note: Optional[str] = Field(None, max_length=2000)


class EmployeeRttSoldeUpdate(BaseModel):
    rtt_solde: float = Field(..., ge=0, le=100)
    note: Optional[str] = Field(None, max_length=2000)


class LeaveAdjustmentImportRow(BaseModel):
    email: Optional[str] = None
    matricule: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    cp_n1_solde: float = 0.0
    cp_n_solde: float = 0.0
    rtt_solde: float = 0.0
    year: int


class LeaveAdjustmentImportRequest(BaseModel):
    rows: List[LeaveAdjustmentImportRow]


class RttYearEndCloseRequest(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    employee_ids: List[str] = Field(..., min_length=1)
