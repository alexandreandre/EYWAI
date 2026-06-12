from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ScheduledExportCreate(BaseModel):
    name: str = Field(..., min_length=1)
    export_type: str
    frequency: Literal["daily", "weekly", "monthly"]
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    hour_utc: int = Field(6, ge=0, le=23)
    recipients: List[str] = Field(default_factory=list)


class ScheduledExportUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    export_type: Optional[str] = None
    frequency: Optional[Literal["daily", "weekly", "monthly"]] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=28)
    hour_utc: Optional[int] = Field(None, ge=0, le=23)
    recipients: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ScheduledExportOut(BaseModel):
    id: str
    company_id: str
    name: str
    export_type: str
    export_type_label: str
    frequency: str
    frequency_label: str
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    hour_utc: int
    recipients: List[str] = Field(default_factory=list)
    is_active: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime


class ScheduledExportRunNowResponse(BaseModel):
    export_id: str
    message: str
    email_status: Optional[str] = None
    email_message: Optional[str] = None
