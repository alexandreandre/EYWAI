from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator

WEBHOOK_EVENTS = [
    "employee.hired",
    "employee.left",
    "employee.salary_updated",
    "payslip.validated",
    "absence.approved",
    "document.signed",
    "recruitment.hired",
]

_WEBHOOK_SET = frozenset(WEBHOOK_EVENTS)


class WebhookConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    name: str
    url: str
    events: List[str]
    is_active: bool
    last_triggered_at: datetime | None
    last_status_code: int | None
    created_at: datetime


class WebhookLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    webhook_id: str
    event_type: str
    response_status: int | None
    duration_ms: int | None
    created_at: datetime


class WebhookCreate(BaseModel):
    name: str
    url: HttpUrl
    secret: str | None = None
    events: List[str]

    @field_validator("events")
    @classmethod
    def events_subset(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Au moins un événement est requis.")
        bad = [e for e in v if e not in _WEBHOOK_SET]
        if bad:
            raise ValueError(f"Événements non supportés : {', '.join(bad)}")
        return v


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: HttpUrl | None = None
    secret: str | None = None
    events: List[str] | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def events_subset(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if not v:
            raise ValueError("Au moins un événement est requis.")
        bad = [e for e in v if e not in _WEBHOOK_SET]
        if bad:
            raise ValueError(f"Événements non supportés : {', '.join(bad)}")
        return v


class WebhookTestResponse(BaseModel):
    status_code: int
    success: bool
