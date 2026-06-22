"""Schémas de requête certifications / habilitations."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class CertificationRefCreate(BaseModel):
    name: str
    code: Optional[str] = None
    category: str
    validity_months: Optional[int] = None
    alert_days: int = 60
    certifying_body: Optional[str] = None
    description: Optional[str] = None
    legal_link: Optional[str] = None


class CertificationRefUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    validity_months: Optional[int] = None
    alert_days: Optional[int] = None
    certifying_body: Optional[str] = None
    description: Optional[str] = None
    legal_link: Optional[str] = None
    status: Optional[str] = None


class EmployeeCertificationCreate(BaseModel):
    employee_id: str
    certification_id: str
    obtained_date: date
    expiry_date: Optional[date] = None
    certifying_body: Optional[str] = None
    certificate_number: Optional[str] = None
    notes: Optional[str] = None


class EmployeeCertificationUpdate(BaseModel):
    """Mise à jour partielle ; l’employé lié n’est pas modifiable."""

    certification_id: Optional[str] = None
    obtained_date: Optional[date] = None
    expiry_date: Optional[date] = None
    certifying_body: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_url: Optional[str] = None
    notes: Optional[str] = None
    is_archived: Optional[bool] = None
