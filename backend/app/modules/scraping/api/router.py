"""
Router du module scraping.

Appelle uniquement la couche application (queries, commands).
Aucune logique métier ni accès DB ; conversion des exceptions applicatives en HTTP.
Comportement HTTP identique au routeur legacy.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.scraping.api.dependencies import verify_super_admin
from app.modules.scraping.application import commands, queries
from app.modules.scraping.schemas import (
    AlertResolve,
    ScheduleCreate,
    ScheduleUpdate,
    ScraperExecutionRequest,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/scraping", tags=["Scraping"])

T = TypeVar("T")

_NOT_FOUND = (
    "Source non trouvée",
    "Job non trouvé",
    "Alerte non trouvée",
    "Planification non trouvée",
)
_BAD_REQUEST = (
    "Cette source est désactivée",
    "Expression cron requise",
    "Intervalle en jours requis",
    "Aucune donnée à mettre à jour",
)


def _to_http(e: Exception) -> HTTPException:
    msg = str(e)
    if msg in _NOT_FOUND:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    if msg in _BAD_REQUEST or "requis" in msg or "non disponible" in msg:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    if isinstance(e, FileNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur : {msg}"
    )


def _app(call: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Appelle l'application et convertit toute exception en HTTPException."""
    try:
        return call(*args, **kwargs)
    except Exception as e:
        raise _to_http(e)


# --- Dashboard & statistiques ---


@router.get("/dashboard")
async def get_scraping_dashboard(super_admin: dict = Depends(verify_super_admin)):
    """Récupère les statistiques globales du système de scraping."""
    return _app(queries.get_scraping_dashboard)


# --- Sources ---


@router.get("/sources")
async def list_sources(
    source_type: Optional[str] = None,
    is_critical: Optional[bool] = None,
    is_active: Optional[bool] = None,
    super_admin: dict = Depends(verify_super_admin),
):
    """Liste toutes les sources de scraping avec leurs statistiques."""
    return _app(
        queries.list_sources,
        source_type=source_type,
        is_critical=is_critical,
        is_active=is_active,
    )


@router.get("/sources/{source_id}")
async def get_source_details(
    source_id: str,
    super_admin: dict = Depends(verify_super_admin),
):
    """Récupère les détails complets d'une source."""
    return _app(queries.get_source_details, source_id)


# --- Exécution ---


@router.post("/execute")
async def execute_scraper(
    request: ScraperExecutionRequest,
    background_tasks: BackgroundTasks,
    super_admin: dict = Depends(verify_super_admin),
    current_user: User = Depends(get_current_user),
):
    """Lance l'exécution d'un scraper et retourne le job_id."""
    return _app(
        commands.execute_scraper,
        source_key=request.source_key,
        scraper_name=request.scraper_name,
        use_orchestrator=request.use_orchestrator,
        triggered_by=current_user.id,
        background_task_fn=background_tasks.add_task,
    )


# --- Jobs ---


@router.get("/jobs")
async def list_jobs(
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    super_admin: dict = Depends(verify_super_admin),
):
    """Liste les jobs de scraping avec filtres."""
    return _app(
        queries.list_jobs,
        source_id=source_id,
        status=status,
        success=success,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}")
async def get_job_details(
    job_id: str,
    super_admin: dict = Depends(verify_super_admin),
):
    """Récupère les détails complets d'un job."""
    return _app(queries.get_job_details, job_id)


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    super_admin: dict = Depends(verify_super_admin),
):
    """Récupère uniquement les logs d'un job (pour le polling)."""
    return _app(queries.get_job_logs, job_id)


# --- Schedules ---


@router.get("/schedules")
async def list_schedules(
    is_enabled: Optional[bool] = None,
    super_admin: dict = Depends(verify_super_admin),
):
    """Liste toutes les planifications."""
    return _app(queries.list_schedules, is_enabled=is_enabled)


@router.post("/schedules")
async def create_schedule(
    schedule: ScheduleCreate,
    super_admin: dict = Depends(verify_super_admin),
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle planification."""
    return _app(
        commands.create_schedule,
        source_id=schedule.source_id,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_days=schedule.interval_days,
        notify_on_success=schedule.notify_on_success,
        notify_on_failure=schedule.notify_on_failure,
        notification_emails=schedule.notification_emails,
        created_by=current_user.id,
    )


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    update: ScheduleUpdate,
    super_admin: dict = Depends(verify_super_admin),
):
    """Met à jour une planification."""
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    return _app(commands.update_schedule, schedule_id, update_data)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    super_admin: dict = Depends(verify_super_admin),
):
    """Supprime une planification."""
    return _app(commands.delete_schedule, schedule_id)


# --- Alertes ---


@router.get("/alerts")
async def list_alerts(
    is_read: Optional[bool] = None,
    is_resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    super_admin: dict = Depends(verify_super_admin),
):
    """Liste les alertes avec filtres."""
    return _app(
        queries.list_alerts,
        is_read=is_read,
        is_resolved=is_resolved,
        severity=severity,
        limit=limit,
    )


@router.patch("/alerts/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: str,
    super_admin: dict = Depends(verify_super_admin),
):
    """Marque une alerte comme lue."""
    return _app(commands.mark_alert_as_read, alert_id)


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution: AlertResolve,
    super_admin: dict = Depends(verify_super_admin),
    current_user: User = Depends(get_current_user),
):
    """Résout une alerte."""
    return _app(
        commands.resolve_alert,
        alert_id,
        resolved_by=current_user.id,
        resolution_note=resolution.resolution_note,
    )
