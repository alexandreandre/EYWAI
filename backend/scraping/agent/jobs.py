"""File d'attente scraping_repair_jobs (Supabase)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client

from agent.models import agent_disabled

logger = logging.getLogger(__name__)

REPAIR_JOBS_TABLE = "scraping_repair_jobs"
ALERTS_TABLE = "scraping_alerts"

VALID_TRIGGERS = (
    "orchestrator_failure",
    "tripwire_change",
    "ci_dry_run_failure",
    "parser_repair",
    "manual",
    "source_url_invalid",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_repair_job(
    supabase: Client,
    *,
    scraper_name: str,
    trigger: str,
    source_id: Optional[str] = None,
    error_message: str = "",
    context: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Insère un job queued ; ignore si un job actif existe déjà pour ce scraper."""
    if agent_disabled():
        logger.debug("Agent réparation désactivé — skip enqueue (%s)", scraper_name)
        return None

    if trigger not in VALID_TRIGGERS:
        trigger = "manual"

    try:
        existing = (
            supabase.table(REPAIR_JOBS_TABLE)
            .select("id")
            .eq("scraper_name", scraper_name)
            .in_("status", ["queued", "running"])
            .limit(1)
            .execute()
        )
        if existing.data:
            logger.info("Job repair déjà actif pour %s — skip enqueue", scraper_name)
            return None
    except Exception as exc:
        logger.warning("Vérification job actif échouée: %s", exc)

    row: dict[str, Any] = {
        "scraper_name": scraper_name,
        "source_id": source_id,
        "trigger": trigger,
        "status": "queued",
        "error_message": error_message[:4000] if error_message else None,
        "context": context or {},
        "attempts": 0,
        "created_at": _iso_now(),
    }
    try:
        resp = supabase.table(REPAIR_JOBS_TABLE).insert(row).execute()
        logger.info("Job repair enqueued pour %s (trigger=%s)", scraper_name, trigger)
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("enqueue_repair_job(%s): %s", scraper_name, exc)
        return None


def claim_next_job(supabase: Client) -> Optional[dict[str, Any]]:
    """Récupère le prochain job queued (FIFO)."""
    try:
        resp = (
            supabase.table(REPAIR_JOBS_TABLE)
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        job = resp.data[0]
        supabase.table(REPAIR_JOBS_TABLE).update(
            {"status": "running", "started_at": _iso_now()}
        ).eq("id", job["id"]).execute()
        job["status"] = "running"
        return job
    except Exception as exc:
        logger.warning("claim_next_job: %s", exc)
        return None


def update_job(
    supabase: Client,
    job_id: str,
    **fields: Any,
) -> None:
    try:
        supabase.table(REPAIR_JOBS_TABLE).update(fields).eq("id", job_id).execute()
    except Exception as exc:
        logger.warning("update_job(%s): %s", job_id, exc)


def emit_repair_alert(
    supabase: Client,
    *,
    alert_type: str,
    scraper_name: str,
    source_id: Optional[str],
    title: str,
    message: str,
    details: Optional[dict[str, Any]] = None,
    severity: str = "info",
) -> None:
    try:
        supabase.table(ALERTS_TABLE).insert(
            {
                "source_id": source_id,
                "alert_type": alert_type,
                "severity": severity,
                "title": title,
                "message": message,
                "details": details or {"scraper_name": scraper_name},
            }
        ).execute()
    except Exception as exc:
        logger.warning("emit_repair_alert: %s", exc)
