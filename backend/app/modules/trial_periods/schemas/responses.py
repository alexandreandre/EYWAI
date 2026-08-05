"""Sorties d'API des périodes d'essai."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TrialPeriod(BaseModel):
    id: str
    company_id: str
    employee_id: str
    employee_name: Optional[str] = None
    start_date: date
    duration_value: int
    duration_unit: str
    renewal_allowed: bool
    renewed_at: Optional[date] = None
    renewal_duration_value: Optional[int] = None
    renewal_duration_unit: Optional[str] = None
    end_date: date
    status: str
    confirmed_at: Optional[datetime] = None
    hire_date: Optional[date] = None
    contract_type: Optional[str] = None
    statut: Optional[str] = None


class TrialPeriodTracking(BaseModel):
    alert_days: int
    en_cours: List[TrialPeriod]
    a_confirmer: List[TrialPeriod]
    a_qualifier: List[Dict[str, Any]]
