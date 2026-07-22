"""
Exécution des scripts de scraping (subprocess).

Contient le mapping source_key -> dossier, la résolution du chemin du script,
et l'exécution avec capture des logs et mise à jour du job (comportement identique au legacy).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.core.paths import SCRAPING_ROOT

from app.modules.scraping.infrastructure.repository import ScrapingRepository

logger = get_logger("modules.scraping")

_ACTIVE_PROCESSES: Dict[str, subprocess.Popen] = {}
_CANCEL_REQUESTED: set[str] = set()
_process_lock = threading.Lock()

_LOG_FLUSH_EVERY_N_LINES = 3
_HEARTBEAT_INTERVAL_SEC = 15
_ORCHESTRATOR_TIMEOUT_SEC = 600
_PID_LOG_RE = re.compile(r"\bpid[:\s]+(\d+)\b", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_scraper_process_active(job_id: str) -> bool:
    """True si un subprocess scraping est encore actif pour ce job."""
    with _process_lock:
        process = _ACTIVE_PROCESSES.get(job_id)
        return process is not None and process.poll() is None


def extract_pid_from_logs(logs: Optional[list]) -> Optional[int]:
    for line in reversed(logs or []):
        match = _PID_LOG_RE.search(str(line))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def is_os_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def is_job_process_active(job_id: str, logs: Optional[list] = None) -> bool:
    """True si le subprocess est suivi en mémoire ou si le pid des logs est encore vivant."""
    if is_scraper_process_active(job_id):
        return True
    pid = extract_pid_from_logs(logs)
    return pid is not None and is_os_process_alive(pid)

# Aligné sur api/routers/scraping.py : certains source_key ne correspondent pas au nom du dossier
SOURCE_KEY_TO_FOLDER_MAPPING = {
    "ALLOCATIONS_FAMILIALES": "alloc",
    "ASSURANCE_CHOMAGE": "assurancechomage",
    "FRAIS_PRO": "fraispro",
    "VIEILLESSE_PATRONAL": "vieillessepatronal",
    "VIEILLESSE_SALARIAL": "vieillessesalarial",
    "MMID_PATRONAL": "MMIDpatronal",
    "MMID_SALARIAL": "MMIDsalarial",
    "IJ_MALADIE": "IJmaladie",
    "DIALOGUE_SOCIAL": "dialoguesocial",
    "TAXE_APPRENTISSAGE": "taxeapprentissage",
    "BAREME_INDEMNITE_KILOMETRIQUE": "bareme-indemnite-kilometrique",
    "SAISIE_ARRET": "saisie-arret",
    "PREVOYANCE_CADRE": "prevoyance",
    "PREVOYANCE_NON_CADRE": "prevoyance",
    "VM": "versement_mobilite",
    "ALTERNANCE": "alternance",
}


def is_job_cancel_requested(job_id: str) -> bool:
    with _process_lock:
        return job_id in _CANCEL_REQUESTED


def clear_cancel_request(job_id: str) -> None:
    with _process_lock:
        _CANCEL_REQUESTED.discard(job_id)


def cancel_scraper_job(
    job_id: str,
    repository: Optional[ScrapingRepository] = None,
) -> bool:
    """Demande l'arrêt d'un job (kill subprocess si actif, statut cancelled en base)."""
    repo = repository or ScrapingRepository()
    with _process_lock:
        _CANCEL_REQUESTED.add(job_id)
        process = _ACTIVE_PROCESSES.get(job_id)

    if process is not None and process.poll() is None:
        try:
            process.kill()
            process.wait(timeout=10)
        except Exception as exc:
            logger.warning("Kill job %s: %s", job_id, exc)
        with _process_lock:
            _ACTIVE_PROCESSES.pop(job_id, None)

    job = repo.get_job(job_id)
    if not job:
        clear_cancel_request(job_id)
        return False

    if job.get("status") in ("pending", "running"):
        repo.update_job(
            job_id,
            {
                "status": "cancelled",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": "Annulé par l'utilisateur",
            },
        )
        clear_cancel_request(job_id)
        return True

    clear_cancel_request(job_id)
    return False


def reset_scraper_runner_state_for_tests() -> None:
    """Vide les registres en mémoire (tests uniquement)."""
    with _process_lock:
        _ACTIVE_PROCESSES.clear()
        _CANCEL_REQUESTED.clear()


def get_scraper_folder_name(source_key: str) -> str:
    """Retourne le nom du dossier de scraping correspondant au source_key."""
    if source_key in SOURCE_KEY_TO_FOLDER_MAPPING:
        return SOURCE_KEY_TO_FOLDER_MAPPING[source_key]
    return source_key.replace("_", "").replace("-", "")


def resolve_script_path(
    source_data: Dict[str, Any],
    scraper_name: Optional[str] = None,
    use_orchestrator: bool = True,
) -> tuple[Path, str]:
    """
    Retourne (chemin_absolu_script, script_type).
    script_type = "orchestrator" | "single_scraper".
    Aligné sur api/routers/scraping.py : racine = backend_api (SCRAPING_ROOT.parent).
    """
    root = Path(SCRAPING_ROOT)
    backend_api_root = root.parent
    orchestrator_path = source_data.get("orchestrator_path")
    available = source_data.get("available_scrapers") or []

    if orchestrator_path and (use_orchestrator or not scraper_name):
        path = backend_api_root / orchestrator_path
        return (path.resolve(), "orchestrator")

    if scraper_name:
        if scraper_name not in available:
            raise ValueError(
                f"Scraper '{scraper_name}' non disponible pour cette source"
            )
        folder = get_scraper_folder_name(source_data["source_key"])
        path = root / folder / scraper_name
        return (path.resolve(), "single_scraper")

    if orchestrator_path:
        path = backend_api_root / orchestrator_path
        return (path.resolve(), "orchestrator")

    if not available:
        raise ValueError(
            f"Aucun scraper disponible pour la source {source_data.get('source_key')}"
        )
    folder = get_scraper_folder_name(source_data["source_key"])
    path = root / folder / available[0]
    return (path.resolve(), "single_scraper")


def _format_subprocess_log_line(line: str, *, from_stderr: bool) -> str:
    """Préfixe stderr seulement pour les vraies erreurs (logging Python → stderr)."""
    if not from_stderr:
        return line
    upper = line.upper()
    if (
        "ERREUR" in upper
        or "[ERROR]" in upper
        or "[CRITICAL]" in upper
        or "TRACEBACK" in upper
        or "❌" in line
        or "✗" in line
    ):
        return f"[ERREUR] {line}"
    if "[WARNING]" in upper or "AVERTISSEMENT" in upper:
        return f"[AVERT] {line}"
    return line


def _display_subprocess_log(source_name: str, log_line: str) -> None:
    """Affiche une ligne de log scraping de façon lisible dans le terminal."""
    logger.info("[scraping:%s] %s", source_name, log_line)


def _handle_review_required(
    repo: ScrapingRepository,
    *,
    job_id: str,
    source_data: Dict[str, Any],
    data_extracted: Dict[str, Any],
) -> None:
    """Tier critique : un changement attend une validation humaine.

    Crée une alerte de revue (source_id connu côté API) et rattache le source_id
    au changement en attente déposé par l'orchestrateur (déposé sans source_id en CLI).
    """
    source_id = source_data.get("id")
    source_name = source_data.get("source_name") or source_data.get("source_key") or ""
    config_key = data_extracted.get("config_key")
    decision_case = data_extracted.get("decision_case")
    ai_candidate = data_extracted.get("ai_candidate")

    try:
        repo.backfill_pending_source_id(config_key, source_id)
    except Exception as exc:
        logger.warning("Backfill source_id du pending (%s): %s", config_key, exc)

    try:
        severity = "critical" if source_data.get("is_critical") else "warning"
        repo.create_alert(
            {
                "job_id": job_id,
                "source_id": source_id,
                "alert_type": "review_required",
                "severity": severity,
                "title": f"Validation requise : {source_name}",
                "message": (
                    "Un changement de taux critique attend une validation humaine "
                    "avant écriture (Revue mensuelle)."
                ),
                "details": {
                    "config_key": config_key,
                    "decision_case": decision_case,
                    "sources_agreement": data_extracted.get("sources_agreement"),
                    "ai_candidate": ai_candidate,
                    "warnings": data_extracted.get("warnings"),
                },
            }
        )
    except Exception as exc:
        logger.warning("Création alerte review_required (%s): %s", config_key, exc)


def run_scraper_script(
    source_data: Dict[str, Any],
    scraper_name: Optional[str],
    use_orchestrator: bool,
    triggered_by: str,
    job_id: Optional[str] = None,
    repository: Optional[ScrapingRepository] = None,
    sync_cotisation_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Exécute le script (subprocess), met à jour le job (logs, statut, alerte si échec).
    Comportement identique à execute_scraper_script du routeur legacy.
    Retourne dict avec job_id, success, duration_ms, error_message, data_extracted.
    """
    repo = repository or ScrapingRepository()
    script_path_obj, script_type = resolve_script_path(
        source_data, scraper_name, use_orchestrator
    )
    script_path = str(script_path_obj)

    if not Path(script_path).exists():
        raise FileNotFoundError(f"Script non trouvé : {script_path}")

    if job_id is not None and is_job_cancel_requested(job_id):
        repo.update_job(
            job_id,
            {
                "status": "cancelled",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": "Annulé par l'utilisateur",
            },
        )
        clear_cancel_request(job_id)
        return {
            "job_id": job_id,
            "success": False,
            "error_message": "Annulé par l'utilisateur",
        }

    source_key = source_data.get("source_key") or ""
    source_name = source_data.get("source_name") or source_key
    start_log = f"Démarrage — {source_name}"

    if job_id is None:
        job_data = {
            "source_id": source_data["id"],
            "job_type": "manual",
            "scraper_used": script_type,
            "triggered_by": triggered_by,
            "status": "running",
            "started_at": utc_now_iso(),
            "execution_logs": [start_log],
        }
        created = repo.create_job(job_data)
        job_id = created["id"]
        logs: list = [start_log]
    else:
        existing = repo.get_job(job_id) or {}
        prior = list(existing.get("execution_logs") or [])
        if start_log not in prior:
            prior.append(start_log)
        repo.update_job(
            job_id,
            {
                "execution_logs": prior,
                "started_at": utc_now_iso(),
            },
        )
        logs = list(prior)

    logger.info("Job %s créé — scraping %s (%s)", job_id, source_name, script_path)

    start_time = datetime.now(timezone.utc)
    logs_lock = threading.Lock()

    def update_logs_in_db() -> None:
        with logs_lock:
            current_logs = list(logs)
        try:
            repo.update_job(job_id, {"execution_logs": current_logs})
        except Exception as e:

            logger.warning("Mise à jour des logs job %s: %s", job_id, e)

    def read_output(pipe, from_stderr: bool = False) -> None:
        try:
            while True:
                line = pipe.readline()
                if not line:
                    break
                line = line.rstrip("\n\r")
                if line:
                    log_line = _format_subprocess_log_line(line, from_stderr=from_stderr)
                    should_flush = False
                    with logs_lock:
                        logs.append(log_line)
                        should_flush = len(logs) % _LOG_FLUSH_EVERY_N_LINES == 0
                    _display_subprocess_log(source_name, log_line)
                    if should_flush:
                        update_logs_in_db()
        except Exception as e:

            logger.warning("Lecture des logs job %s: %s", job_id, e)
        finally:
            pipe.close()

    process_env = __import__("os").environ.copy()
    process_env["PYTHONUNBUFFERED"] = "1"
    if sync_cotisation_ids:
        process_env["EYWAI_SYNC_COTISATION_IDS"] = ",".join(sync_cotisation_ids)
    else:
        process_env.pop("EYWAI_SYNC_COTISATION_IDS", None)

    process = subprocess.Popen(
        [sys.executable, "-u", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(script_path_obj.parent),
        env=process_env,
    )
    with _process_lock:
        _ACTIVE_PROCESSES[job_id] = process

    logger.info(
        "[scraping:%s] Processus lancé (pid %s)",
        source_name,
        process.pid,
    )
    with logs_lock:
        logs.append(f"Processus lancé (pid {process.pid})")
    update_logs_in_db()

    stop_heartbeat = threading.Event()

    def _progress_heartbeat() -> None:
        while not stop_heartbeat.wait(_HEARTBEAT_INTERVAL_SEC):
            if process.poll() is not None:
                break
            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds())
            with logs_lock:
                last = logs[-1] if logs else "initialisation…"
            if len(last) > 100:
                last = last[:97] + "…"
            logger.info(
                "[scraping:%s] ⏳ En cours (%ds) — %s",
                source_name,
                elapsed,
                last,
            )
            heartbeat_line = f"⏳ En cours ({elapsed}s) — {last}"
            should_flush = False
            with logs_lock:
                if not logs or logs[-1] != heartbeat_line:
                    logs.append(heartbeat_line)
                    should_flush = True
            if should_flush:
                update_logs_in_db()

    heartbeat_thread = threading.Thread(target=_progress_heartbeat, daemon=True)
    heartbeat_thread.start()

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout,))
    stdout_thread.start()

    return_code: int
    was_cancelled = False
    try:
        if is_job_cancel_requested(job_id):
            process.kill()
            process.wait(timeout=10)
            was_cancelled = True
            return_code = -1
        else:
            return_code = process.wait(timeout=_ORCHESTRATOR_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return_code = -1
        with logs_lock:
            logs.append(
                f"[ERREUR] Le script a dépassé le délai d'exécution ({_ORCHESTRATOR_TIMEOUT_SEC // 60} minutes)"
            )
        error_msg = (
            f"Le script a dépassé le délai d'exécution ({_ORCHESTRATOR_TIMEOUT_SEC // 60} minutes)"
        )

        logger.warning("Job %s TIMEOUT: %s", job_id, error_msg)
        repo.update_job(
            job_id,
            {
                "status": "failed",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": error_msg,
            },
        )
        return {
            "job_id": job_id,
            "success": False,
            "error_message": error_msg,
        }
    finally:
        stop_heartbeat.set()
        if not was_cancelled:
            was_cancelled = is_job_cancel_requested(job_id)
        with _process_lock:
            _ACTIVE_PROCESSES.pop(job_id, None)
        clear_cancel_request(job_id)
        heartbeat_thread.join(timeout=1)

    stdout_thread.join(timeout=2)
    update_logs_in_db()

    if was_cancelled:
        repo.update_job(
            job_id,
            {
                "status": "cancelled",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": "Annulé par l'utilisateur",
            },
        )
        return {
            "job_id": job_id,
            "success": False,
            "error_message": "Annulé par l'utilisateur",
        }

    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)

    success = return_code == 0
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    data_extracted: Optional[dict] = None

    if success:
        for log_line in reversed(logs):
            if log_line.strip().startswith("{"):
                try:
                    data_extracted = json.loads(log_line)
                    logs.append("[SUCCÈS] Données extraites avec succès")
                    break
                except json.JSONDecodeError:
                    continue

    if not success:
        error_message = f"Le script a retourné le code {return_code}"
        error_lines = [log for log in logs if "[ERREUR]" in log]
        if error_lines:
            error_stack = "\n".join(error_lines)

    with logs_lock:
        final_logs = list(logs)

    update_data = {
        "status": "completed" if success else "failed",
        "completed_at": end_time.isoformat(),
        "duration_ms": duration_ms,
        "success": success,
        "execution_logs": final_logs,
        "data_extracted": data_extracted,
        "error_message": error_message,
        "error_stack": error_stack,
    }

    # Cartographie des métadonnées de décision v2 vers les colonnes du job.
    requires_review = False
    if isinstance(data_extracted, dict):
        requires_review = bool(data_extracted.get("requires_review"))
        proposed_value = data_extracted.get("proposed_value")
        current_value = data_extracted.get("current_value")
        if proposed_value is not None or current_value is not None:
            update_data["data_before"] = current_value
            update_data["data_after"] = proposed_value
            update_data["changes_detected"] = {
                "from": current_value,
                "to": proposed_value,
            }
        if "sources_agreement" in data_extracted:
            update_data["sources_agreement"] = data_extracted.get("sources_agreement")
        if "discrepancies" in data_extracted:
            update_data["discrepancies"] = data_extracted.get("discrepancies")
        update_data["validation_results"] = {
            "decision_case": data_extracted.get("decision_case"),
            "tier": data_extracted.get("tier"),
            "requires_review": requires_review,
            "ai_candidate": data_extracted.get("ai_candidate"),
            "warnings": data_extracted.get("warnings"),
        }

    repo.update_job(job_id, update_data)

    if success and requires_review:
        _handle_review_required(
            repo,
            job_id=job_id,
            source_data=source_data,
            data_extracted=data_extracted or {},
        )

    if not success:
        stderr_content = getattr(process.stderr, "read", lambda: None)()
        alert_data = {
            "job_id": job_id,
            "source_id": source_data["id"],
            "alert_type": "failure",
            "severity": "error" if source_data.get("is_critical") else "warning",
            "title": f"Échec du scraping: {source_data['source_name']}",
            "message": error_message or "Le scraping a échoué",
            "details": {
                "script_path": script_path,
                "return_code": process.returncode,
                "stderr": (stderr_content[:500] if stderr_content else None),
            },
        }
        repo.create_alert(alert_data)


    logger.info(
        "Job %s terminé — %s success=%s duration_ms=%s%s",
        job_id,
        source_name,
        success,
        duration_ms,
        f" error={error_message}" if error_message else "",
    )

    return {
        "job_id": job_id,
        "success": success,
        "duration_ms": duration_ms,
        "data_extracted": data_extracted,
        "error_message": error_message,
    }


def apply_pending_change_sync(
    pending_id: str,
    reviewed_by: Optional[str] = None,
    timeout_sec: int = 120,
) -> Dict[str, Any]:
    """Lance core/apply_pending_change.py en subprocess (service key) et attend.

    Retourne {"success": bool, "logs": [...], "error": str|None}.
    """
    script_path = Path(SCRAPING_ROOT) / "core" / "apply_pending_change.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Script apply introuvable : {script_path}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if reviewed_by:
        env["EYWAI_REVIEWED_BY"] = str(reviewed_by)

    try:
        result = subprocess.run(
            [sys.executable, "-u", str(script_path), pending_id],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(SCRAPING_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "logs": [],
            "error": f"Application du changement expirée après {timeout_sec}s",
        }

    logs = [line for line in (result.stdout or "").splitlines() if line.strip()]
    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[-1000:]
        logger.warning(
            "apply_pending_change %s échec (code %s): %s",
            pending_id,
            result.returncode,
            stderr_tail,
        )
        return {
            "success": False,
            "logs": logs,
            "error": stderr_tail or f"Code de sortie {result.returncode}",
        }
    return {"success": True, "logs": logs, "error": None}


def run_tripwire_background(
    source_data: Dict[str, Any],
    job_id: str,
    repository: Optional[ScrapingRepository] = None,
) -> None:
    """Lance core/tripwire.py <source_key> et met à jour le job (n'écrit pas payroll_config)."""
    repo = repository or ScrapingRepository()
    source_key = source_data.get("source_key") or ""
    source_name = source_data.get("source_name") or source_key
    script_path = Path(SCRAPING_ROOT) / "core" / "tripwire.py"
    start_time = datetime.now(timezone.utc)

    if not script_path.exists():
        repo.update_job(
            job_id,
            {
                "status": "failed",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": f"Script tripwire introuvable : {script_path}",
            },
        )
        return

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(script_path), source_key],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SCRAPING_ROOT),
            env=env,
        )
    except subprocess.TimeoutExpired:
        repo.update_job(
            job_id,
            {
                "status": "failed",
                "completed_at": utc_now_iso(),
                "success": False,
                "error_message": "Tripwire expiré (300s)",
            },
        )
        return

    logs = [line for line in (result.stdout or "").splitlines() if line.strip()]
    logs += [
        _format_subprocess_log_line(line, from_stderr=True)
        for line in (result.stderr or "").splitlines()
        if line.strip()
    ]
    success = result.returncode == 0
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    repo.update_job(
        job_id,
        {
            "status": "completed" if success else "failed",
            "completed_at": utc_now_iso(),
            "duration_ms": duration_ms,
            "success": success,
            "execution_logs": logs,
            "error_message": None if success else f"Code de sortie {result.returncode}",
        },
    )
    logger.info("Tripwire %s terminé (success=%s)", source_name, success)


def run_scraper_script_background(
    source_data: Dict[str, Any],
    scraper_name: Optional[str],
    use_orchestrator: bool,
    triggered_by: str,
    job_id: str,
    repository: Optional[ScrapingRepository] = None,
    sync_cotisation_ids: Optional[List[str]] = None,
) -> None:
    """
    Wrapper pour BackgroundTasks : appelle run_scraper_script et en cas d'exception
    (avant ou pendant l'exécution) met à jour le job en failed.
    """
    repo = repository or ScrapingRepository()
    if is_job_cancel_requested(job_id):
        try:
            repo.update_job(
                job_id,
                {
                    "status": "cancelled",
                    "completed_at": utc_now_iso(),
                    "success": False,
                    "error_message": "Annulé par l'utilisateur",
                },
            )
        except Exception:
            pass
        clear_cancel_request(job_id)
        return
    try:
        run_scraper_script(
            source_data,
            scraper_name,
            use_orchestrator,
            triggered_by,
            job_id,
            repository=repo,
            sync_cotisation_ids=sync_cotisation_ids,
        )
    except Exception as e:
        error_msg = f"Erreur lors de l'exécution : {str(e)}"
        error_trace = traceback.format_exc()

        logger.error("Job %s ERREUR: %s\n%s", job_id, error_msg, error_trace)
        try:
            repo.update_job(
                job_id,
                {
                    "status": "failed",
                    "completed_at": utc_now_iso(),
                    "success": False,
                    "error_message": error_msg,
                    "error_stack": error_trace,
                },
            )
        except Exception:
            pass
