"""
Requêtes métier complexes scraping (enrichissement sources, dashboard, etc.).

Agrégation et enrichissement via le repository ; pas de logique métier pure
(règles métier dans domain/). Comportement identique au legacy.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.scraping.infrastructure.repository import ScrapingRepository


def get_dashboard_data(repo: ScrapingRepository) -> Dict[str, Any]:
    """
    Stats + recent_jobs + unread_alerts + critical_sources (avec last_job par source).
    Même structure de retour que le routeur legacy.
    """
    stats = repo.get_scraping_stats()
    recent_jobs = repo.get_recent_jobs(limit=10)
    unread_alerts = repo.get_unread_alerts(limit=5)
    critical_sources = repo.get_critical_sources()
    for source in critical_sources:
        source["last_job"] = repo.get_last_job_for_source(source["id"])
    return {
        "stats": stats,
        "recent_jobs": recent_jobs,
        "unread_alerts": unread_alerts,
        "critical_sources": critical_sources,
    }


def list_sources_enriched(
    repo: ScrapingRepository,
    source_type: Optional[str] = None,
    is_critical: Optional[bool] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Liste des sources avec last_job, success_rate_30d, unresolved_alerts_count.
    Retourne {"sources": [...], "total": n}.
    """
    sources = repo.list_sources(
        source_type=source_type,
        is_critical=is_critical,
        is_active=is_active,
    )
    for source in sources:
        source_id = source["id"]
        source["last_job"] = repo.get_last_job_for_source(source_id)
        jobs_30d, count = repo.get_jobs_for_source_30d(source_id)
        if count and count > 0:
            successful = sum(1 for j in jobs_30d if j.get("success") is True)
            source["success_rate_30d"] = round(100 * successful / count, 2)
        else:
            source["success_rate_30d"] = None
        source["unresolved_alerts_count"] = repo.get_unresolved_alerts_count(source_id)
    return {"sources": sources, "total": len(sources)}


def get_source_details_enriched(
    repo: ScrapingRepository,
    source_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Source + jobs_history + schedules + recent_alerts.
    Retourne None si la source n'existe pas.
    """
    source = repo.get_source_by_id(source_id)
    if not source:
        return None
    source["jobs_history"] = repo.get_jobs_history_for_source(source_id, limit=20)
    source["schedules"] = repo.get_schedules_for_source(source_id)
    source["recent_alerts"] = repo.get_recent_alerts_for_source(source_id, limit=10)
    return source
