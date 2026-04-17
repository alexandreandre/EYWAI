"""Schémas de réponse certifications / habilitations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ComputedStatus = Literal["valid", "expiring_soon", "expired", "no_expiry"]


class CertificationRef(BaseModel):
    id: str
    company_id: str
    name: str
    code: Optional[str] = None
    category: str
    validity_months: Optional[int] = None
    alert_days: int = 60
    certifying_body: Optional[str] = None
    description: Optional[str] = None
    legal_link: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class EmployeeCertification(BaseModel):
    id: str
    company_id: str
    employee_id: str
    certification_id: str
    obtained_date: date
    expiry_date: Optional[date] = None
    certifying_body: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_url: Optional[str] = None
    notes: Optional[str] = None
    is_archived: bool = False
    created_at: Optional[datetime] = None
    computed_status: ComputedStatus
    certification_ref: Optional[CertificationRef] = None
    employee_name: Optional[str] = None


class DashboardCounts(BaseModel):
    expiring: int = Field(ge=0)
    expired: int = Field(ge=0)


__all__ = ["CertificationRef", "ComputedStatus", "DashboardCounts", "EmployeeCertification"]
