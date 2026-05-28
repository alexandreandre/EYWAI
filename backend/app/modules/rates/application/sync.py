"""
Synchronisation des taux réglementaires pour les utilisateurs RH.

Lance les scrapers via le module scraping, par source, catégorie ou ligne de cotisation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.modules.rates.domain.rate_source_mapping import (
    COTISATION_ID_TO_SOURCE_KEYS,
    RATE_KEY_TO_SOURCE_KEYS,
    normalize_source_key,
    resolve_source_keys,
)
from app.modules.scraping.application.commands import execute_scraper
from app.modules.scraping.infrastructure.repository import ScrapingRepository
from app.modules.scraping.infrastructure.scraper_runner import cancel_scraper_job
from app.modules.rates.application.sync_progress import compute_batch_progress

_ERR_NO_SOURCES = "Aucune source active trouvée pour cette mise à jour."
_ERR_SYNC_NOT_FOUND = "Synchronisation non trouvée."
_ERR_SOURCES_BUSY = "Une mise à jour est déjà en cours pour : {keys}"

_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_RUNNING_STATUSES = frozenset({"pending", "running"})

_SYNC_BATCHES: Dict[str, Dict[str, Any]] = {}
# source_key normalisé -> sync_id en cours
_RUNNING_BY_SOURCE: Dict[str, str] = {}


def _repo() -> ScrapingRepository:
    return ScrapingRepository()


def _find_source_by_key(sources: List[Dict[str, Any]], source_key: str) -> Optional[Dict[str, Any]]:
    target = normalize_source_key(source_key)
    for src in sources:
        if normalize_source_key(src.get("source_key", "")) == target:
            return src
    return None


def _sources_for_keys(requested_keys: List[str]) -> List[Dict[str, Any]]:
    """Résout les lignes scraping_sources actives pour les clés demandées."""
    repo = _repo()
    active = repo.list_sources(is_active=True)
    if not requested_keys:
        return repo.get_critical_sources()

    matched: List[Dict[str, Any]] = []
    missing: List[str] = []
    for key in requested_keys:
        src = _find_source_by_key(active, key)
        if src:
            matched.append(src)
        else:
            missing.append(key)
    if missing and not matched:
        raise ValueError(
            f"Aucune source active pour : {', '.join(missing)}"
        )
    return matched


def _register_running_sources(sync_id: str, source_keys: List[str]) -> None:
    for sk in source_keys:
        _RUNNING_BY_SOURCE[normalize_source_key(sk)] = sync_id


def _unregister_batch(sync_id: str) -> None:
    to_remove = [k for k, sid in _RUNNING_BY_SOURCE.items() if sid == sync_id]
    for k in to_remove:
        _RUNNING_BY_SOURCE.pop(k, None)


def _assert_sources_available(source_keys: List[str]) -> None:
    busy = [
        sk
        for sk in source_keys
        if normalize_source_key(sk) in _RUNNING_BY_SOURCE
    ]
    if busy:
        raise ValueError(_ERR_SOURCES_BUSY.format(keys=", ".join(busy)))


def get_rates_sync_sources_manifest() -> Dict[str, Any]:
    """
    Manifeste des unités mettables à jour (pour l’UI).
    Ne retourne que les sources actives présentes en base.
    """
    repo = _repo()
    active = repo.list_sources(is_active=True)
    active_by_norm = {
        normalize_source_key(s["source_key"]): s for s in active
    }

    def pack_source(source_key: str) -> Optional[Dict[str, Any]]:
        src = active_by_norm.get(normalize_source_key(source_key))
        if not src:
            return None
        norm = normalize_source_key(source_key)
        running = norm in _RUNNING_BY_SOURCE
        return {
            "source_key": src["source_key"],
            "source_name": src.get("source_name", source_key),
            "is_running": running,
        }

    rate_categories: List[Dict[str, Any]] = []
    for rate_key, source_keys in RATE_KEY_TO_SOURCE_KEYS.items():
        sources = [s for sk in source_keys if (s := pack_source(sk))]
        entry: Dict[str, Any] = {
            "rate_key": rate_key,
            "sources": sources,
        }
        if rate_key == "cotisations":
            cotisation_units = []
            for cid, sks in COTISATION_ID_TO_SOURCE_KEYS.items():
                cot_sources = [s for sk in sks if (s := pack_source(sk))]
                if cot_sources:
                    cotisation_units.append(
                        {"cotisation_id": cid, "sources": cot_sources}
                    )
            entry["cotisation_units"] = cotisation_units
        rate_categories.append(entry)

    return {
        "rate_categories": rate_categories,
        "all_critical_count": len(repo.get_critical_sources()),
    }


def start_rates_sync(
    triggered_by: str,
    background_task_fn: Callable[..., None],
    *,
    rate_keys: Optional[List[str]] = None,
    source_keys: Optional[List[str]] = None,
    cotisation_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Démarre une mise à jour ciblée ou globale (sources critiques si aucun filtre).
    """
    requested = resolve_source_keys(
        rate_keys=rate_keys,
        source_keys=source_keys,
        cotisation_ids=cotisation_ids,
    )

    sources = _sources_for_keys(requested)
    if not sources:
        raise ValueError(_ERR_NO_SOURCES)

    keys_to_run = [s["source_key"] for s in sources]
    _assert_sources_available(keys_to_run)

    sync_id = str(uuid.uuid4())
    jobs: List[Dict[str, Any]] = []

    for source in sources:
        source_key = source["source_key"]
        use_orchestrator = bool(source.get("orchestrator_path"))
        try:
            result = execute_scraper(
                source_key=source_key,
                use_orchestrator=use_orchestrator,
                triggered_by=triggered_by,
                background_task_fn=background_task_fn,
            )
            jobs.append(
                {
                    "source_key": source_key,
                    "source_name": result.get("source") or source.get("source_name", source_key),
                    "job_id": result["job_id"],
                    "status": "running",
                    "error_message": None,
                    "rate_keys": _rate_keys_for_source(source_key),
                }
            )
        except Exception as exc:
            jobs.append(
                {
                    "source_key": source_key,
                    "source_name": source.get("source_name", source_key),
                    "job_id": None,
                    "status": "failed",
                    "error_message": str(exc),
                    "rate_keys": _rate_keys_for_source(source_key),
                }
            )

    _SYNC_BATCHES[sync_id] = {
        "sync_id": sync_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": triggered_by,
        "jobs": jobs,
        "target": {
            "rate_keys": rate_keys,
            "source_keys": source_keys,
            "cotisation_ids": cotisation_ids,
        },
    }
    _register_running_sources(sync_id, keys_to_run)

    return {
        "sync_id": sync_id,
        "jobs": jobs,
        "total": len(jobs),
        "message": "Mise à jour des taux lancée",
    }


def _rate_keys_for_source(source_key: str) -> List[str]:
    norm = normalize_source_key(source_key)
    keys: List[str] = []
    for rk, sks in RATE_KEY_TO_SOURCE_KEYS.items():
        if any(normalize_source_key(sk) == norm for sk in sks):
            keys.append(rk)
    return keys


def cancel_rates_sync(sync_id: str) -> Dict[str, Any]:
    """Annule un lot en cours : libère les sources et stoppe les jobs scraping actifs."""
    batch = _SYNC_BATCHES.get(sync_id)
    if not batch:
        raise ValueError(_ERR_SYNC_NOT_FOUND)

    if batch.get("cancelled"):
        return get_rates_sync_status(sync_id)

    batch["cancelled"] = True
    for entry in batch["jobs"]:
        job_id = entry.get("job_id")
        if job_id:
            cancel_scraper_job(job_id)
            entry["status"] = "cancelled"
            entry["error_message"] = "Annulé par l'utilisateur"
        elif entry.get("status") in _RUNNING_STATUSES:
            entry["status"] = "cancelled"
            entry["error_message"] = "Annulé par l'utilisateur"

    _unregister_batch(sync_id)
    return get_rates_sync_status(sync_id)


def get_rates_sync_status(sync_id: str) -> Dict[str, Any]:
    """Agrège l'état des jobs d'un lot de synchronisation."""
    batch = _SYNC_BATCHES.get(sync_id)
    if not batch:
        raise ValueError(_ERR_SYNC_NOT_FOUND)

    if batch.get("cancelled"):
        jobs = list(batch.get("jobs", []))
        progress_detail = compute_batch_progress(jobs, batch_created_at=batch.get("created_at"))
        enriched_jobs = progress_detail.pop("jobs")
        progress_detail["percent"] = 100
        progress_detail["percent_exact"] = 100.0
        progress_detail["eta_seconds"] = None
        return {
            "sync_id": sync_id,
            "status": "cancelled",
            "progress": progress_detail,
            "jobs": enriched_jobs,
            "created_at": batch["created_at"],
            "target": batch.get("target"),
        }

    repo = _repo()
    updated_jobs: List[Dict[str, Any]] = []
    counts = {"completed": 0, "failed": 0, "running": 0, "total": len(batch["jobs"])}

    for entry in batch["jobs"]:
        job_id = entry.get("job_id")
        if not job_id:
            updated_jobs.append(dict(entry))
            counts["failed"] += 1
            continue

        job = repo.get_job(job_id)
        if not job:
            updated_jobs.append(
                {
                    **entry,
                    "status": "failed",
                    "error_message": "Job introuvable",
                }
            )
            counts["failed"] += 1
            continue

        status = job.get("status") or "pending"
        success = job.get("success")
        item = {
            "source_key": entry["source_key"],
            "source_name": entry["source_name"],
            "job_id": job_id,
            "status": status,
            "success": success,
            "error_message": job.get("error_message"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "execution_logs": job.get("execution_logs") or [],
            "rate_keys": entry.get("rate_keys", []),
        }
        updated_jobs.append(item)

        if status in _RUNNING_STATUSES:
            counts["running"] += 1
        elif status == "cancelled":
            counts["failed"] += 1
        elif status == "completed" and success:
            counts["completed"] += 1
        elif status == "completed" and success is False:
            counts["failed"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status in _TERMINAL_STATUSES:
            if success:
                counts["completed"] += 1
            else:
                counts["failed"] += 1

    batch["jobs"] = updated_jobs

    if batch.get("cancelled"):
        overall = "cancelled"
    elif counts["running"] > 0:
        overall = "running"
    elif counts["failed"] == counts["total"]:
        overall = "failed"
    elif counts["failed"] > 0:
        overall = "completed_with_errors"
    else:
        overall = "completed"

    progress_detail = compute_batch_progress(
        updated_jobs,
        batch_created_at=batch.get("created_at"),
    )
    enriched_jobs = progress_detail.pop("jobs")

    if overall in ("completed", "completed_with_errors", "failed", "cancelled"):
        progress_detail["percent"] = 100
        progress_detail["percent_exact"] = 100.0
        progress_detail["eta_seconds"] = None
        _unregister_batch(sync_id)

    return {
        "sync_id": sync_id,
        "status": overall,
        "progress": progress_detail,
        "jobs": enriched_jobs,
        "created_at": batch["created_at"],
        "target": batch.get("target"),
    }


def reset_sync_registry_for_tests() -> None:
    """Vide le registre (tests unitaires uniquement)."""
    _SYNC_BATCHES.clear()
    _RUNNING_BY_SOURCE.clear()
