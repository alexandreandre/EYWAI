"""Schémas persistance batch import pointages."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.schedules.schemas.ai import AiDayEntry


class PersistTimesheetEmployee(BaseModel):
    employee_id: str
    days: List[AiDayEntry] = Field(default_factory=list)


class PersistTimesheetRequest(BaseModel):
    year: int
    month: int
    employees: List[PersistTimesheetEmployee] = Field(default_factory=list)
    batch_id: Optional[str] = None
    recalculate_payroll: bool = False
    allow_partial: bool = False


class PersistTimesheetResult(BaseModel):
    employee_id: str
    days_written: int
    success: bool
    error: Optional[str] = None


class PersistTimesheetResponse(BaseModel):
    year: int
    month: int
    employees_processed: int
    total_days_written: int
    results: List[PersistTimesheetResult] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)
    # Ce qui n'a délibérément PAS été appliqué (ex. jour d'absence validée
    # qu'un relevé d'heures voulait requalifier) — à afficher au RH.
    warnings: List[dict] = Field(default_factory=list)


__all__ = [
    "PersistTimesheetEmployee",
    "PersistTimesheetRequest",
    "PersistTimesheetResponse",
    "PersistTimesheetResult",
]
