"""
Estimation fine de l'avancement d'une sync taux (logs scraping + durée).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Durée médiane par défaut si aucun historique (scraping + écriture config)
DEFAULT_JOB_DURATION_SEC = 90
MAX_JOB_DURATION_SEC = 300

_LOG_STAGE_RULES: Tuple[Tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"initialisation|lancé en arrière", re.I), 0.06),
    (re.compile(r"démarrage de l'exécution|démarrage", re.I), 0.12),
    (re.compile(r"scraping de l'url|recherche ddgs|tentative sur", re.I), 0.28),
    (re.compile(r"analyse url|extraction ia|fetch|chargé depuis", re.I), 0.42),
    (re.compile(r"extraction réussie|taux trouv|données extraites|complète", re.I), 0.72),
    (re.compile(r"\[succès\]|succès", re.I), 0.88),
    (re.compile(r"terminé|job .* terminé", re.I), 0.95),
)

_NOISE_PREFIXES = ("[ERREUR]", "ERREUR", "AVERTISSEMENT", "WARNING")


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


def _sanitize_log_line(line: str, max_len: int = 120) -> str:
    text = line.strip()
    for prefix in _NOISE_PREFIXES:
        if text.upper().startswith(prefix):
            text = text[len(prefix) :].strip(" :")
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def infer_progress_from_logs(logs: List[str]) -> Tuple[float, str]:
    """
    Déduit une fraction 0–1 et un libellé d'étape à partir des logs du job.
    """
    if not logs:
        return 0.05, "Démarrage du script…"

    stage_score = 0.05
    for line in logs:
        for pattern, score in _LOG_STAGE_RULES:
            if pattern.search(line):
                stage_score = max(stage_score, score)

    line_bonus = min(0.2, len(logs) * 0.004)
    fraction = min(0.92, stage_score + line_bonus)

    last_meaningful = ""
    for line in reversed(logs):
        cleaned = _sanitize_log_line(line)
        if cleaned and not cleaned.startswith("{"):
            last_meaningful = cleaned
            break

    if not last_meaningful:
        last_meaningful = "Traitement en cours…"

    return fraction, last_meaningful


def infer_progress_from_elapsed(
    started_at: Optional[str],
    *,
    expected_duration_sec: float = DEFAULT_JOB_DURATION_SEC,
) -> float:
    started = _parse_iso(started_at)
    if not started:
        return 0.08
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if elapsed <= 0:
        return 0.08
    return min(0.88, elapsed / min(expected_duration_sec, MAX_JOB_DURATION_SEC))


def job_duration_seconds(job: Dict[str, Any]) -> Optional[float]:
    started = _parse_iso(job.get("started_at"))
    completed = _parse_iso(job.get("completed_at"))
    if not started or not completed:
        return None
    return max(1.0, (completed - started).total_seconds())


def estimate_job_fraction(
    job: Dict[str, Any],
    *,
    avg_completed_duration: float,
) -> Tuple[float, str]:
    """
    Fraction de complétion d'un job (0–1) et libellé courant.
    """
    status = (job.get("status") or "pending").lower()
    success = job.get("success")

    if status in ("completed", "failed", "cancelled"):
        return 1.0, job.get("current_step") or ("Terminé" if success else "Terminé avec erreur")

    if status == "pending":
        return 0.03, "En file d'attente…"

    logs = job.get("execution_logs") or []
    if isinstance(logs, str):
        logs = [logs]
    log_fraction, step = infer_progress_from_logs(list(logs))
    time_fraction = infer_progress_from_elapsed(
        job.get("started_at"),
        expected_duration_sec=avg_completed_duration,
    )
    fraction = max(log_fraction, time_fraction * 0.55)
    return min(0.95, fraction), step


def compute_batch_progress(
    jobs: List[Dict[str, Any]],
    *,
    batch_created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Agrège la progression d'un lot : pourcentage lissé, étape courante, ETA.
    """
    total = len(jobs) or 1
    completed_durations: List[float] = []
    for raw in jobs:
        if raw.get("status") in ("completed", "failed", "cancelled"):
            dur = job_duration_seconds(raw)
            if dur:
                completed_durations.append(dur)

    avg_duration = (
        sum(completed_durations) / len(completed_durations)
        if completed_durations
        else DEFAULT_JOB_DURATION_SEC
    )

    enriched: List[Dict[str, Any]] = []
    fraction_sum = 0.0
    current_source: Optional[str] = None
    current_step = "Initialisation…"
    remaining_sec = 0.0

    for entry in jobs:
        item = dict(entry)
        frac, step = estimate_job_fraction(item, avg_completed_duration=avg_duration)
        item["progress_fraction"] = round(frac, 3)
        item["current_step"] = step
        logs = item.get("execution_logs") or []
        if logs and isinstance(logs, list):
            item["last_log_line"] = _sanitize_log_line(str(logs[-1]))
        fraction_sum += frac

        status = (item.get("status") or "pending").lower()
        if status in ("running", "pending") and current_source is None:
            current_source = item.get("source_name") or item.get("source_key")
            if status == "running":
                current_step = step

        if status in ("running", "pending"):
            remaining_sec += (1.0 - frac) * avg_duration

        enriched.append(item)

    percent_exact = (fraction_sum / total) * 100.0
    percent = int(min(99, percent_exact)) if percent_exact < 100 else 100

    eta_seconds: Optional[int] = None
    if remaining_sec > 3 and percent < 100:
        eta_seconds = int(max(5, remaining_sec))

    terminal = ("completed", "failed", "cancelled")
    completed_ok = sum(
        1 for j in jobs if j.get("status") == "completed" and j.get("success") is not False
    )
    failed = sum(
        1
        for j in jobs
        if j.get("status") in ("failed", "cancelled")
        or (j.get("status") == "completed" and j.get("success") is False)
    )
    running = sum(1 for j in jobs if (j.get("status") or "") == "running")
    pending = sum(1 for j in jobs if (j.get("status") or "") == "pending")
    done = sum(1 for j in jobs if (j.get("status") or "") in terminal)

    return {
        "percent": percent,
        "percent_exact": round(percent_exact, 1),
        "done": done,
        "total": total,
        "completed": completed_ok,
        "failed": failed,
        "running": running,
        "pending": pending,
        "current_source": current_source,
        "current_step": current_step,
        "eta_seconds": eta_seconds,
        "avg_job_duration_sec": int(avg_duration),
        "jobs": enriched,
    }
