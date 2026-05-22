"""Schémas de réponse pour GET /api/dashboard/analytics-gestion."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsGestionPeriod(BaseModel):
    period_start: str
    period_end: str
    year: int
    calendar_year: int
    calendar_month: int


class EntretiensAnalytics(BaseModel):
    actionable_count: int = 0
    overdue_count: int = 0
    upcoming_14d_count: int = 0
    closure_rate_pct: float = 0.0
    by_status: Dict[str, int] = Field(default_factory=dict)


class ConformiteAnalytics(BaseModel):
    certifications_expired: int = 0
    certifications_expiring: int = 0
    legal_obligations_overdue: int = 0
    legal_obligations_due_soon: int = 0
    legal_obligations_up_to_date: int = 0


class FormationAnalytics(BaseModel):
    budget_consumption_pct: float = 0.0
    budget_alert_level: str = "none"
    budget_consumed: float = 0.0
    budget_envelope: float = 0.0
    training_consumed_year: float = 0.0
    evaluations_count: int = 0
    evaluations_average: Optional[float] = None


class CalendriersAnalytics(BaseModel):
    total: int = 0
    saisis: int = 0
    a_saisir: int = 0
    avec_ecart: int = 0
    conflits_absences: int = 0
    progress_percent: int = 0


class MedicalAnalytics(BaseModel):
    overdue_count: int = 0
    due_within_30_count: int = 0
    active_total: int = 0
    completed_this_month: int = 0
    compliance_rate_pct: float = 0.0
    employees_overdue_top: List[Dict[str, object]] = Field(default_factory=list)


class ObjectivesAnalytics(BaseModel):
    achievement_rate_pct: Optional[float] = None


class CarriereAnalytics(BaseModel):
    total_promotions: int = 0
    approval_rate_pct: float = 0.0
    average_salary_increase_pct: Optional[float] = None
    promotions_by_month: Dict[str, int] = Field(default_factory=dict)
    promotions_draft_count: int = 0
    avenants_pending_signature: int = 0


class CseMeetingPreview(BaseModel):
    id: str
    title: str
    meeting_date: str
    meeting_time: Optional[str] = None


class CseAnalytics(BaseModel):
    mandate_alerts_count: int = 0
    election_alerts_count: int = 0
    election_critical_count: int = 0
    delegation_over_quota_count: int = 0
    delegation_consumed_hours: float = 0.0
    delegation_quota_hours: float = 0.0
    upcoming_meetings: List[CseMeetingPreview] = Field(default_factory=list)


class AnalyticsGestionResponse(BaseModel):
    period: AnalyticsGestionPeriod
    entretiens: EntretiensAnalytics
    conformite: ConformiteAnalytics
    formation: FormationAnalytics
    calendriers: CalendriersAnalytics
    medical: MedicalAnalytics
    objectives: ObjectivesAnalytics
    carriere: CarriereAnalytics
    cse: CseAnalytics
