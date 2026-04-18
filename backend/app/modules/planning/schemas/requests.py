"""Schémas de requête Pydantic v2 — module Planning."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, field_validator, model_validator


class ShiftCreate(BaseModel):
    employee_id: str
    shift_type_id: Optional[str] = None
    transverse_category: Optional[str] = None
    shift_date: date
    start_time: time
    end_time: time
    post: Optional[str] = None
    location: Optional[str] = None
    comment_internal: Optional[str] = None
    comment_employee: Optional[str] = None

    @model_validator(mode="after")
    def validate_category(self) -> ShiftCreate:
        if not self.shift_type_id and not self.transverse_category:
            raise ValueError("shift_type_id ou transverse_category requis")
        if self.shift_type_id and self.transverse_category:
            raise ValueError("shift_type_id et transverse_category mutuellement exclusifs")
        if self.end_time <= self.start_time:
            raise ValueError("end_time doit être après start_time")
        return self


class ShiftUpdate(BaseModel):
    shift_type_id: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    post: Optional[str] = None
    location: Optional[str] = None
    comment_internal: Optional[str] = None
    comment_employee: Optional[str] = None


class WeekDuplicateRequest(BaseModel):
    source_week_start: date
    target_weeks: List[date]
    include_comments: bool = True
    skip_locked_days: bool = True
    skip_absent_employees: bool = True

    @field_validator("source_week_start", "target_weeks", mode="before")
    @classmethod
    def must_be_monday(cls, v: object) -> object:
        if v is None:
            return v

        def _to_date(x: object) -> date:
            if isinstance(x, datetime):
                return x.date()
            if isinstance(x, date):
                return x
            if isinstance(x, str):
                return date.fromisoformat(x[:10])
            raise ValueError("Valeur de date invalide")

        if isinstance(v, list):
            out: List[date] = []
            for item in v:
                d = _to_date(item)
                if d.weekday() != 0:
                    raise ValueError("Chaque date cible doit être un lundi")
                out.append(d)
            return out
        d = _to_date(v)
        if d.weekday() != 0:
            raise ValueError("source_week_start doit être un lundi")
        return d


class WeekLockRequest(BaseModel):
    week_start: date
    reason: Optional[str] = None


class DayLockRequest(BaseModel):
    day_date: date
    reason: Optional[str] = None


class WeekPublishRequest(BaseModel):
    week_start: date
    publish_days: Optional[List[date]] = None


class CompanyPlanningSettingsUpdate(BaseModel):
    collective_agreement_id: Optional[str] = None
    team_view_default: Optional[bool] = None
