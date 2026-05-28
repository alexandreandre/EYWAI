"""
Exécution des scripts de scraping (subprocess).

Contient le mapping source_key -> dossier, la résolution du chemin du script,
et l'exécution avec capture des logs et mise à jour du job (comportement identique au legacy).
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.core.paths import SCRAPING_ROOT

from app.modules.scraping.infrastructure.repository import ScrapingRepository

logger = get_logger("modules.scraping")

_ACTIVE_PROCESSES: Dict[str, subprocess.Popen] = {}
_CANCEL_REQUESTED: set[str] = set()
_process_lock = threading.Lock()

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
                "completed_at": datetime.now().isoformat(),
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


def run_scraper_script(
    source_data: Dict[str, Any],
    scraper_name: Optional[str],
    use_orchestrator: bool,
    triggered_by: str,
    job_id: Optional[str] = None,
    repository: Optional[ScrapingRepository] = None,
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
                "completed_at": datetime.now().isoformat(),
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

    if job_id is None:
        job_data = {
            "source_id": source_data["id"],
            "job_type": "manual",
            "scraper_used": script_type,
            "triggered_by": triggered_by,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "execution_logs": [f"Démarrage de l'exécution de {script_path}"],
        }
        created = repo.create_job(job_data)
        job_id = created["id"]
    else:
        repo.update_job(
            job_id,
            {"execution_logs": [f"Démarrage de l'exécution de {script_path}"]},
        )


    logger.info("Job %s créé — exécution de %s", job_id, script_path)

    start_time = datetime.now()
    logs: list = []
    logs_lock = threading.Lock()

    def update_logs_in_db() -> None:
        with logs_lock:
            current_logs = list(logs)
        try:
            repo.update_job(job_id, {"execution_logs": current_logs})
        except Exception as e:

            logger.warning("Mise à jour des logs job %s: %s", job_id, e)

    def read_output(pipe, log_prefix: str = "") -> None:
        try:
            while True:
                line = pipe.readline()
                if not line:
                    break
                line = line.rstrip("\n\r")
                if line:
                    log_line = f"{log_prefix}{line}" if log_prefix else line
                    with logs_lock:
                        logs.append(log_line)
                    with logs_lock:
                        if len(logs) % 10 == 0:
                            update_logs_in_db()
        except Exception as e:

            logger.warning("Lecture des logs job %s: %s", job_id, e)
        finally:
            pipe.close()

    process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(script_path_obj.parent),
        env=__import__("os").environ.copy(),
    )
    with _process_lock:
        _ACTIVE_PROCESSES[job_id] = process

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, ""))
    stderr_thread = threading.Thread(
        target=read_output, args=(process.stderr, "[ERREUR] ")
    )
    stdout_thread.start()
    stderr_thread.start()

    return_code: int
    was_cancelled = False
    try:
        if is_job_cancel_requested(job_id):
            process.kill()
            process.wait(timeout=10)
            was_cancelled = True
            return_code = -1
        else:
            return_code = process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return_code = -1
        with logs_lock:
            logs.append("[ERREUR] Le script a dépassé le délai d'exécution (5 minutes)")
        error_msg = "Le script a dépassé le délai d'exécution (5 minutes)"

        logger.warning("Job %s TIMEOUT: %s", job_id, error_msg)
        repo.update_job(
            job_id,
            {
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
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
        if not was_cancelled:
            was_cancelled = is_job_cancel_requested(job_id)
        with _process_lock:
            _ACTIVE_PROCESSES.pop(job_id, None)
        clear_cancel_request(job_id)

    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)

    if was_cancelled:
        repo.update_job(
            job_id,
            {
                "status": "cancelled",
                "completed_at": datetime.now().isoformat(),
                "success": False,
                "error_message": "Annulé par l'utilisateur",
            },
        )
        return {
            "job_id": job_id,
            "success": False,
            "error_message": "Annulé par l'utilisateur",
        }

    end_time = datetime.now()
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
    repo.update_job(job_id, update_data)

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
        "Job %s terminé — success=%s duration_ms=%s",
        job_id,
        success,
        duration_ms,
    )

    return {
        "job_id": job_id,
        "success": success,
        "duration_ms": duration_ms,
        "data_extracted": data_extracted,
        "error_message": error_message,
    }


def run_scraper_script_background(
    source_data: Dict[str, Any],
    scraper_name: Optional[str],
    use_orchestrator: bool,
    triggered_by: str,
    job_id: str,
    repository: Optional[ScrapingRepository] = None,
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
                    "completed_at": datetime.now().isoformat(),
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
                    "completed_at": datetime.now().isoformat(),
                    "success": False,
                    "error_message": error_msg,
                    "error_stack": error_trace,
                },
            )
        except Exception:
            pass
