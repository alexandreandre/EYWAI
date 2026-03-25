"""
Commandes (cas d'usage écriture) du module scraping.

Délégation au repository et au scraper_runner ; validation métier via domain.rules.
Comportement identique au routeur legacy.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from app.modules.scraping.domain.rules import (
    require_source_for_execution,
    validate_schedule_create,
    validate_schedule_update,
)
from app.modules.scraping.infrastructure.repository import ScrapingRepository
from app.modules.scraping.infrastructure.scraper_runner import (
    resolve_script_path,
    run_scraper_script_background,
)


def _repo() -> ScrapingRepository:
    return ScrapingRepository()


def execute_scraper(
    source_key: str,
    scraper_name: Optional[str] = None,
    use_orchestrator: bool = True,
    triggered_by: str = "",
    background_task_fn: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """
    Lance l'exécution d'un scraper : récupère la source, crée le job, lance le script en arrière-plan.
    Retourne dict avec message, source_name, source_key, job_id.
    """
    repo = _repo()
    source = repo.get_source_by_key(source_key)
    require_source_for_execution(source)

    script_path_obj, script_type = resolve_script_path(
        source, scraper_name, use_orchestrator
    )
    script_path = str(script_path_obj)

    job_data = {
        "source_id": source["id"],
        "job_type": "manual",
        "scraper_used": script_type,
        "triggered_by": triggered_by,
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "execution_logs": [f"Initialisation du job - Script: {script_path}"],
    }
    created = repo.create_job(job_data)
    job_id = created["id"]
    repo.update_job(job_id, {"status": "running"})

    if background_task_fn:
        background_task_fn(
            run_scraper_script_background,
            source,
            scraper_name,
            use_orchestrator,
            triggered_by,
            job_id,
        )

    return {
        "message": "Scraping lancé en arrière-plan",
        "source": source["source_name"],
        "source_key": source_key,
        "job_id": job_id,
    }


def create_schedule(
    source_id: str,
    schedule_type: str,
    cron_expression: Optional[str] = None,
    interval_days: Optional[int] = None,
    notify_on_success: bool = False,
    notify_on_failure: bool = True,
    notification_emails: Optional[list] = None,
    created_by: str = "",
) -> Dict[str, Any]:
    """Crée une planification. Validation métier dans domain.rules."""
    validate_schedule_create(schedule_type, cron_expression, interval_days)

    if schedule_type == "interval" and interval_days:
        next_run_at = datetime.now() + timedelta(days=interval_days)
    else:
        next_run_at = datetime.now() + timedelta(days=1)

    schedule_data = {
        "source_id": source_id,
        "schedule_type": schedule_type,
        "cron_expression": cron_expression,
        "interval_days": interval_days,
        "is_enabled": True,
        "next_run_at": next_run_at.isoformat(),
        "notify_on_success": notify_on_success,
        "notify_on_failure": notify_on_failure,
        "notification_emails": notification_emails or [],
        "created_by": created_by,
    }
    repo = _repo()
    schedule = repo.create_schedule(schedule_data)
    return {"success": True, "schedule": schedule}


def update_schedule(schedule_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Met à jour une planification."""
    validate_schedule_update(update_data)
    repo = _repo()
    schedule = repo.update_schedule(schedule_id, update_data)
    if schedule is None:
        raise ValueError("Planification non trouvée")
    return {"success": True, "schedule": schedule}


def delete_schedule(schedule_id: str) -> Dict[str, Any]:
    """Supprime une planification."""
    repo = _repo()
    ok = repo.delete_schedule(schedule_id)
    if not ok:
        raise ValueError("Planification non trouvée")
    return {"success": True, "message": "Planification supprimée"}


def mark_alert_as_read(alert_id: str) -> Dict[str, Any]:
    """Marque une alerte comme lue."""
    repo = _repo()
    ok = repo.mark_alert_read(alert_id)
    if not ok:
        raise ValueError("Alerte non trouvée")
    return {"success": True}


def resolve_alert(
    alert_id: str,
    resolved_by: str = "",
    resolution_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Résout une alerte."""
    update_data = {
        "is_resolved": True,
        "is_read": True,
        "resolved_at": datetime.now().isoformat(),
        "resolved_by": resolved_by,
        "resolution_note": resolution_note,
    }
    repo = _repo()
    ok = repo.resolve_alert(alert_id, update_data)
    if not ok:
        raise ValueError("Alerte non trouvée")
    return {"success": True}
