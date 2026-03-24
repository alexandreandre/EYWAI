"""
Schémas réponse API du module scraping.

Reflet exact des dict renvoyés par le routeur legacy (api/routers/scraping.py).
Utilisables en response_model ou pour typage ; contenu des listes/dict restant Any
pour ne pas modifier le comportement de sérialisation.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class ScrapingDashboardResponse(BaseModel):
    """GET /dashboard."""

    stats: dict
    recent_jobs: List[Any]
    unread_alerts: List[Any]
    critical_sources: List[Any]


class SourcesListResponse(BaseModel):
    """GET /sources."""

    sources: List[Any]
    total: int


class ExecuteScraperResponse(BaseModel):
    """POST /execute (réponse immédiate)."""

    message: str
    source: str
    source_key: str
    job_id: str


class JobExecutionResultResponse(BaseModel):
    """Résultat synchrone d'exécution (retour interne execute_scraper_script)."""

    job_id: str
    success: Optional[bool] = None
    duration_ms: Optional[int] = None
    data_extracted: Optional[dict] = None
    error_message: Optional[str] = None


class JobsListResponse(BaseModel):
    """GET /jobs."""

    jobs: List[Any]
    total: int


class JobLogsResponse(BaseModel):
    """GET /jobs/{job_id}/logs."""

    job_id: str
    status: str
    logs: List[Any]
    success: Optional[bool] = None
    error_message: Optional[str] = None
    completed_at: Optional[str] = None


class SchedulesListResponse(BaseModel):
    """GET /schedules."""

    schedules: List[Any]
    total: int


class ScheduleMutationResponse(BaseModel):
    """POST /schedules, PATCH /schedules/{id}."""

    success: bool
    schedule: Any


class DeleteScheduleResponse(BaseModel):
    """DELETE /schedules/{id}."""

    success: bool
    message: str


class AlertsListResponse(BaseModel):
    """GET /alerts."""

    alerts: List[Any]
    total: int


class SuccessResponse(BaseModel):
    """PATCH /alerts/{id}/read, PATCH /alerts/{id}/resolve."""

    success: bool
