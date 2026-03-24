"""
Requêtes (cas d'usage lecture) du module scraping.

Délégation à l'infrastructure (repository + queries enrichies).
Règles de "non trouvé" levées ici (ValueError) pour que le routeur convertisse en 404.
Comportement identique au routeur legacy.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.scraping.infrastructure.queries import (
    get_dashboard_data as infra_get_dashboard_data,
    get_source_details_enriched as infra_get_source_details_enriched,
    list_sources_enriched as infra_list_sources_enriched,
)
from app.modules.scraping.infrastructure.repository import ScrapingRepository


def _repo() -> ScrapingRepository:
    return ScrapingRepository()


def get_scraping_dashboard() -> Dict[str, Any]:
    """Stats + recent_jobs + unread_alerts + critical_sources (avec last_job par source)."""
    return infra_get_dashboard_data(_repo())


def list_sources(
    source_type: Optional[str] = None,
    is_critical: Optional[bool] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """Liste les sources avec last_job, success_rate_30d, unresolved_alerts_count."""
    return infra_list_sources_enriched(
        _repo(),
        source_type=source_type,
        is_critical=is_critical,
        is_active=is_active,
    )


def get_source_details(source_id: str) -> Dict[str, Any]:
    """Détails d'une source + jobs_history + schedules + recent_alerts."""
    result = infra_get_source_details_enriched(_repo(), source_id)
    if result is None:
        raise ValueError("Source non trouvée")
    return result


def list_jobs(
    source_id: Optional[str] = None,
    status: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Liste les jobs avec filtres."""
    repo = _repo()
    jobs = repo.list_jobs(
        source_id=source_id,
        status=status,
        success=success,
        limit=limit,
        offset=offset,
    )
    return {"jobs": jobs, "total": len(jobs)}


def get_job_details(job_id: str) -> Dict[str, Any]:
    """Détails complets d'un job (avec source)."""
    repo = _repo()
    job = repo.get_job(job_id)
    if not job:
        raise ValueError("Job non trouvé")
    return job


def get_job_logs(job_id: str) -> Dict[str, Any]:
    """Logs d'un job pour le polling."""
    repo = _repo()
    job = repo.get_job_logs_fields(job_id)
    if not job:
        raise ValueError("Job non trouvé")
    return {
        "job_id": job["id"],
        "status": job["status"],
        "logs": job.get("execution_logs", []),
        "success": job.get("success"),
        "error_message": job.get("error_message"),
        "completed_at": job.get("completed_at"),
    }


def list_schedules(is_enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Liste les planifications."""
    repo = _repo()
    schedules = repo.list_schedules(is_enabled=is_enabled)
    return {"schedules": schedules, "total": len(schedules)}


def list_alerts(
    is_read: Optional[bool] = None,
    is_resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Liste les alertes avec filtres."""
    repo = _repo()
    alerts = repo.list_alerts(
        is_read=is_read,
        is_resolved=is_resolved,
        severity=severity,
        limit=limit,
    )
    return {"alerts": alerts, "total": len(alerts)}
