"""
Synchronisation des taux réglementaires pour les utilisateurs RH.

Lance les scrapers via le module scraping, par source, catégorie ou ligne de cotisation.
"""

from __future__ import annotations

import re
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.modules.rates.domain.rate_source_mapping import (
    COTISATION_ID_TO_SOURCE_KEYS,
    RATE_KEY_TO_SOURCE_KEYS,
    all_page_source_keys,
    normalize_source_key,
    resolve_source_keys,
)
from app.modules.scraping.application.commands import execute_scraper
from app.modules.scraping.infrastructure.repository import ScrapingRepository
from app.modules.scraping.infrastructure.scraper_runner import (
    cancel_scraper_job,
    extract_pid_from_logs,
    is_job_cancel_requested,
    is_job_process_active,
    is_os_process_alive,
)
from app.modules.rates.application.sync_progress import (
    MAX_JOB_DURATION_SEC,
    compute_batch_progress,
)
from app.modules.rates.infrastructure.sync_run_store import (
    MemorySyncRunStore,
    get_sync_run_store,
    set_sync_run_store,
)

_ERR_NO_SOURCES = "Aucune source active trouvée pour cette mise à jour."
_ERR_SYNC_NOT_FOUND = "Synchronisation non trouvée."
_ERR_SOURCES_BUSY = "Une mise à jour est déjà en cours pour : {keys}"

_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_RUNNING_STATUSES = frozenset({"pending", "running"})

# Au-delà : job « running » sans processus actif (redémarrage serveur, crash, timeout non remonté)
_STALE_RUNNING_GRACE_SEC = MAX_JOB_DURATION_SEC + 30
# Processus orphelin (pid mort) : ne pas attendre 10 min
_ORPHAN_PID_GRACE_SEC = 45
# Heartbeat d'un scraper qui tourne sur une autre machine (cron GitHub).
_FOREIGN_HEARTBEAT_GRACE_SEC = 90
_HOST_LOG_RE = re.compile(r"Processus lancé \(pid \d+\) sur (\S+)")
_HEARTBEAT_LOG_RE = re.compile(r"En cours \((\d+)s\)")

_OVERALL_TO_RUN_STATUS = {
    "completed": "succeeded",
    "completed_with_errors": "partial",
    "failed": "failed",
    "cancelled": "cancelled",
}
_STORED_TO_OVERALL = {status: overall for overall, status in _OVERALL_TO_RUN_STATUS.items()}


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        normalized = dt.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _reconcile_completed_job_from_logs(
    repo: ScrapingRepository,
    job_id: str,
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """Rattrape un job laissé « running » alors que les logs indiquent un succès."""
    if (job.get("status") or "").lower() != "running":
        return job

    logs = job.get("execution_logs") or []
    blob = "\n".join(str(line) for line in logs).lower()
    success_markers = (
        "fin orchestrateur",
        '"success": true',
        "données extraites avec succès",
        "last_checked_at' mis à jour",
        "mis à jour vers v",
    )
    if not any(marker in blob for marker in success_markers):
        return job

    now = datetime.now(timezone.utc).isoformat()
    repo.update_job(
        job_id,
        {
            "status": "completed",
            "success": True,
            "completed_at": now,
            "error_message": None,
        },
    )
    refreshed = repo.get_job(job_id)
    return refreshed if refreshed else {**job, "status": "completed", "success": True}


def _execution_host(logs: List[Any]) -> Optional[str]:
    for line in logs:
        match = _HOST_LOG_RE.search(str(line))
        if match:
            return match.group(1)
    return None


def _heartbeat_lag_sec(elapsed: float, logs: List[Any]) -> Optional[float]:
    reported: Optional[int] = None
    for line in reversed(logs):
        match = _HEARTBEAT_LOG_RE.search(str(line))
        if match:
            reported = int(match.group(1))
            break
    if reported is None:
        return None
    return elapsed - reported


def _fail_stale_job(
    repo: ScrapingRepository,
    job_id: str,
    job: Dict[str, Any],
    logs: List[Any],
    msg: str,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    log_lines = list(logs)
    if not any(msg in str(line) for line in log_lines):
        log_lines.append(msg)
    repo.update_job(
        job_id,
        {
            "status": "failed",
            "success": False,
            "completed_at": now,
            "error_message": msg,
            "execution_logs": log_lines,
        },
    )
    refreshed = repo.get_job(job_id)
    return refreshed if refreshed else {**job, "status": "failed", "success": False, "error_message": msg}


def _mark_stale_running_job_if_needed(
    repo: ScrapingRepository,
    job_id: str,
    job: Dict[str, Any],
) -> Dict[str, Any]:
    """Marque en échec un job bloqué en « running » trop longtemps.

    Un scraper lancé sur une autre machine (cron) n'est pas jugé mort parce que
    son pid est absent de ce serveur : on se fie à son heartbeat.
    """
    if (job.get("status") or "").lower() != "running":
        return job

    if is_job_cancel_requested(job_id):
        return job

    logs = job.get("execution_logs") or []
    if is_job_process_active(job_id, logs):
        return job

    started = _parse_iso(job.get("started_at"))
    if not started:
        return job

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if elapsed < 0:
        return job

    host = _execution_host(logs)
    if host and host != socket.gethostname():
        lag = _heartbeat_lag_sec(elapsed, logs)
        if lag is not None and lag < _FOREIGN_HEARTBEAT_GRACE_SEC:
            return job
        if lag is None and elapsed < _STALE_RUNNING_GRACE_SEC:
            return job
        return _fail_stale_job(
            repo,
            job_id,
            job,
            logs,
            (
                "Le traitement s'est interrompu (plus de signal du scraper). "
                "Relancez la mise à jour."
            ),
        )

    pid = extract_pid_from_logs(logs)
    orphan = pid is not None and not is_os_process_alive(pid)

    if orphan and elapsed >= _ORPHAN_PID_GRACE_SEC:
        msg = (
            "Le processus de scraping s'est arrêté de façon inattendue "
            "(redémarrage du serveur ou blocage). Relancez la mise à jour."
        )
    elif elapsed < _STALE_RUNNING_GRACE_SEC:
        return job
    else:
        msg = (
            "Le traitement s'est interrompu (délai dépassé ou redémarrage du serveur). "
            "Relancez la mise à jour."
        )

    return _fail_stale_job(repo, job_id, job, logs, msg)

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
        requested_keys = all_page_source_keys()

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


def _jobs_for_store(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stored: List[Dict[str, Any]] = []
    for job in jobs:
        stored.append(
            {
                "source_key": job.get("source_key"),
                "source_name": job.get("source_name"),
                "job_id": job.get("job_id"),
                "status": job.get("status"),
                "success": job.get("success"),
                "error_message": job.get("error_message"),
                "rate_keys": job.get("rate_keys") or [],
                "cotisation_ids": job.get("cotisation_ids") or [],
            }
        )
    return stored


def _persist_terminal(sync_id: str, overall: str, jobs: List[Dict[str, Any]]) -> None:
    run_status = _OVERALL_TO_RUN_STATUS.get(overall)
    if not run_status:
        return
    get_sync_run_store().update_run(
        sync_id,
        {
            "status": run_status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "jobs": _jobs_for_store(jobs),
        },
    )


def _load_batch(sync_id: str) -> Optional[Dict[str, Any]]:
    """Retrouve un lot. Le process qui l'a lancé garde sa mémoire.

    Un autre process (la page, pendant le cron) relit la ligne à chaque appel :
    la liste des sources grandit au fil de l'eau, et un instantané vide ne doit
    pas rester en mémoire jusqu'à conclure un faux échec.
    """
    batch = _SYNC_BATCHES.get(sync_id)
    if batch and batch.get("process_local"):
        return batch
    row = get_sync_run_store().get_run(sync_id)
    if batch and not row:
        return batch
    if not row:
        return None
    if batch is None:
        batch = {
            "sync_id": sync_id,
            "created_at": row.get("started_at") or row.get("created_at"),
            "triggered_by": row.get("triggered_by"),
            "jobs": [],
            "target": {},
            "cancelled": False,
            "launch_complete": False,
            "process_local": False,
            "source_keys": [],
        }
        _SYNC_BATCHES[sync_id] = batch
    batch["jobs"] = list(row.get("jobs") or [])
    batch["target"] = row.get("target") or batch.get("target") or {}
    batch["cancelled"] = row.get("status") == "cancelled"
    batch["source_keys"] = list(row.get("source_keys") or [])
    batch["stored_status"] = row.get("status")
    batch["created_at"] = row.get("started_at") or row.get("created_at") or batch.get("created_at")
    if row.get("status") == "running":
        keys = batch["source_keys"] or [job.get("source_key") for job in batch["jobs"]]
        _register_running_sources(sync_id, [key for key in keys if key])
    return batch


def _publish_jobs(sync_id: str, jobs: List[Dict[str, Any]]) -> None:
    get_sync_run_store().update_run(sync_id, {"jobs": _jobs_for_store(jobs)})


def _expected_source_count(batch: Dict[str, Any], stored: Optional[Dict[str, Any]]) -> int:
    keys = (stored or {}).get("source_keys") or batch.get("source_keys") or []
    return len([key for key in keys if key])


def _launch_still_open(batch: Dict[str, Any], stored: Optional[Dict[str, Any]]) -> bool:
    """Le lancement n'a pas encore inscrit toutes les sources : ne pas clore le lot."""
    if batch.get("cancelled"):
        return False
    if stored and stored.get("status") == "cancelled":
        return False
    if batch.get("process_local") and not batch.get("launch_complete"):
        return True
    if not stored or stored.get("status") != "running":
        return False
    expected = _expected_source_count(batch, stored)
    jobs = batch.get("jobs") or []
    if expected == 0:
        return not jobs
    return len(jobs) < expected


def _open_launch_progress(
    jobs: List[Dict[str, Any]],
    *,
    created_at: Optional[str],
    expected: int,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    progress = compute_batch_progress(jobs, batch_created_at=created_at)
    enriched = progress.pop("jobs")
    total = expected if expected > len(jobs) else progress["total"]
    if not jobs and expected:
        total = expected
    done = progress.get("done") or 0
    if total:
        exact = done / total * 100.0
    else:
        exact = 0.0
    progress["total"] = total
    progress["percent_exact"] = round(exact, 1)
    progress["percent"] = int(min(99, exact))
    if not jobs:
        progress["current_step"] = "Démarrage…"
        progress["percent"] = 0
        progress["percent_exact"] = 0.0
    return progress, enriched


def _hydrate_running_locks() -> None:
    for row in get_sync_run_store().list_running():
        sync_id = str(row.get("id") or "")
        if not sync_id:
            continue
        if sync_id not in _SYNC_BATCHES:
            _load_batch(sync_id)
            continue
        if row.get("status") == "running":
            keys = row.get("source_keys") or []
            _register_running_sources(sync_id, [key for key in keys if key])


def _bind_background(sync_id: str, background_task_fn: Callable[..., None]) -> Callable[..., None]:
    def _schedule(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        def _run() -> None:
            try:
                fn(*args, **kwargs)
            finally:
                batch = _SYNC_BATCHES.get(sync_id)
                if batch and batch.get("launch_complete"):
                    try:
                        get_rates_sync_status(sync_id)
                    except Exception:
                        pass

        background_task_fn(_run)

    return _schedule


def list_active_page_source_keys() -> List[str]:
    sources = _sources_for_keys(all_page_source_keys())
    return [source["source_key"] for source in sources]


def get_rates_sync_sources_manifest() -> Dict[str, Any]:
    """
    Manifeste des unités mettables à jour (pour l’UI).
    Ne retourne que les sources actives présentes en base.
    """
    _hydrate_running_locks()
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
        primary_url = (src.get("primary_url") or "").strip() or None
        return {
            "source_key": src["source_key"],
            "source_name": src.get("source_name", source_key),
            "primary_url": primary_url,
            "is_running": running,
            "sync_id": _RUNNING_BY_SOURCE.get(norm) if running else None,
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
        "all_critical_count": sum(
            1 for sk in all_page_source_keys() if pack_source(sk)
        ),
    }


def start_rates_sync(
    triggered_by: str,
    background_task_fn: Callable[..., None],
    *,
    rate_keys: Optional[List[str]] = None,
    source_keys: Optional[List[str]] = None,
    cotisation_ids: Optional[List[str]] = None,
    month_key: Optional[str] = None,
    trigger: str = "page",
    forced: bool = False,
) -> Dict[str, Any]:
    """
    Démarre une mise à jour ciblée ou globale (toutes les sources actives de la page si aucun filtre).
    """
    _hydrate_running_locks()
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
    created_at = datetime.now(timezone.utc).isoformat()
    target = {
        "rate_keys": rate_keys,
        "source_keys": source_keys,
        "cotisation_ids": cotisation_ids,
    }
    jobs: List[Dict[str, Any]] = []
    batch: Dict[str, Any] = {
        "sync_id": sync_id,
        "created_at": created_at,
        "triggered_by": triggered_by,
        "jobs": jobs,
        "target": target,
        "launch_complete": False,
        "process_local": True,
        "source_keys": keys_to_run,
    }
    _SYNC_BATCHES[sync_id] = batch
    get_sync_run_store().insert_run(
        {
            "id": sync_id,
            "month_key": month_key,
            "trigger": trigger if trigger in ("schedule", "manual", "page") else "page",
            "status": "running",
            "started_at": created_at,
            "finished_at": None,
            "triggered_by": triggered_by,
            "forced": forced,
            "target": target,
            "source_keys": keys_to_run,
            "jobs": [],
        }
    )
    _register_running_sources(sync_id, keys_to_run)

    cotisation_ids_snapshot = list(cotisation_ids) if cotisation_ids else []
    tracked_background = _bind_background(sync_id, background_task_fn)

    for source in sources:
        stored = get_sync_run_store().get_run(sync_id) or {}
        if batch.get("cancelled") or stored.get("status") == "cancelled":
            batch["cancelled"] = True
            break
        source_key = source["source_key"]
        use_orchestrator = bool(source.get("orchestrator_path"))
        entry: Dict[str, Any] = {
            "source_key": source_key,
            "source_name": source.get("source_name", source_key),
            "job_id": None,
            "status": "running",
            "error_message": None,
            "rate_keys": _rate_keys_for_source(source_key),
            "cotisation_ids": cotisation_ids_snapshot,
        }
        jobs.append(entry)
        # Visible tout de suite : un suivi ouvert pendant ce scraper ne voit pas une liste vide.
        _publish_jobs(sync_id, jobs)
        try:
            result = execute_scraper(
                source_key=source_key,
                use_orchestrator=use_orchestrator,
                triggered_by=triggered_by,
                background_task_fn=tracked_background,
                sync_cotisation_ids=cotisation_ids,
            )
            entry["source_name"] = result.get("source") or entry["source_name"]
            entry["job_id"] = result["job_id"]
            entry["status"] = "running"
            entry["error_message"] = None
        except Exception as exc:
            entry["status"] = "failed"
            entry["error_message"] = str(exc)
        _publish_jobs(sync_id, jobs)

    batch["launch_complete"] = True
    _publish_jobs(sync_id, jobs)

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
    batch = _load_batch(sync_id)
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
    batch = _load_batch(sync_id)
    if not batch:
        raise ValueError(_ERR_SYNC_NOT_FOUND)

    stored = get_sync_run_store().get_run(sync_id)
    if stored and stored.get("status") == "cancelled":
        batch["cancelled"] = True

    if batch.get("cancelled"):
        jobs = list(batch.get("jobs", []))
        progress_detail = compute_batch_progress(jobs, batch_created_at=batch.get("created_at"))
        enriched_jobs = progress_detail.pop("jobs")
        progress_detail["percent"] = 100
        progress_detail["percent_exact"] = 100.0
        progress_detail["eta_seconds"] = None
        _persist_terminal(sync_id, "cancelled", enriched_jobs)
        _unregister_batch(sync_id)
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
            if (entry.get("status") or "") in _RUNNING_STATUSES:
                counts["running"] += 1
            else:
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

        job = _reconcile_completed_job_from_logs(repo, job_id, job)
        job = _mark_stale_running_job_if_needed(repo, job_id, job)

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
            "cotisation_ids": entry.get("cotisation_ids", []),
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

    launch_open = _launch_still_open(batch, stored)
    if batch.get("cancelled"):
        overall = "cancelled"
    elif launch_open or counts["running"] > 0:
        overall = "running"
    elif counts["total"] == 0:
        # Zéro source inscrite n'est pas un échec : le lancement n'a pas encore écrit.
        # Une ligne déjà close reste close, même si sa liste a été vidée.
        mapped = _STORED_TO_OVERALL.get((stored or {}).get("status") or "")
        if mapped:
            overall = mapped
        else:
            overall = "running"
            launch_open = True
    elif counts["failed"] == counts["total"]:
        overall = "failed"
    elif counts["failed"] > 0:
        overall = "completed_with_errors"
    else:
        overall = "completed"

    if launch_open and overall == "running":
        expected = _expected_source_count(batch, stored)
        progress_detail, enriched_jobs = _open_launch_progress(
            updated_jobs,
            created_at=batch.get("created_at"),
            expected=expected,
        )
    else:
        progress_detail = compute_batch_progress(
            updated_jobs,
            batch_created_at=batch.get("created_at"),
        )
        enriched_jobs = progress_detail.pop("jobs")

    if overall in ("completed", "completed_with_errors", "failed", "cancelled") and updated_jobs:
        progress_detail["percent"] = 100
        progress_detail["percent_exact"] = 100.0
        progress_detail["eta_seconds"] = None
        _persist_terminal(sync_id, overall, enriched_jobs)
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
    set_sync_run_store(MemorySyncRunStore())
