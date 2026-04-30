"""Réponses API — notifications."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    employee_id: str | None
    company_id: str
    type: str
    message: str
    is_read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int
