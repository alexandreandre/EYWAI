"""Mise à jour mensuelle des taux : décision, lancement, état affiché sur la page."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.core.logging import get_logger
from app.modules.rates.application.sync import (
    cancel_rates_sync,
    get_rates_sync_status,
    list_active_page_source_keys,
    start_rates_sync,
)
from app.modules.rates.domain.monthly_schedule import (
    StoredMonthlyRun,
    decide_monthly_run,
    describe_monthly_status,
    month_key,
    panel_actions,
    run_button_label,
)
from app.modules.rates.infrastructure.sync_run_store import (
    MonthRunBusy,
    get_sync_run_store,
)
from app.modules.scraping.infrastructure.repository import ScrapingRepository

logger = get_logger("modules.rates.monthly")


def get_monthly_rates_state(now: Optional[datetime] = None) -> Dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    store = get_sync_run_store()
    enabled = store.get_auto_enabled()
    key = month_key(moment)
    rows = store.list_month(key)
    snapshots = _snapshots(rows, moment)
    show_run, show_restart = panel_actions(moment, enabled=enabled, runs=snapshots)
    latest = _latest_row(rows)
    run = None
    if latest:
        run = {
            "sync_id": str(latest["id"]),
            "status": latest.get("status"),
            "started_at": latest.get("started_at"),
            "finished_at": latest.get("finished_at"),
        }
    return {
        "enabled": enabled,
        "month_key": key,
        "status_label": describe_monthly_status(moment, enabled=enabled, runs=snapshots),
        "show_run": show_run,
        "show_restart": show_restart,
        "run_button_label": run_button_label(snapshots),
        "run": run,
    }


def set_monthly_auto_enabled(enabled: bool, now: Optional[datetime] = None) -> Dict[str, Any]:
    get_sync_run_store().set_auto_enabled(enabled)
    return get_monthly_rates_state(now=now)


def launch_monthly_sync(
    *,
    triggered_by: str,
    background_task_fn: Callable[..., None],
    trigger: str,
    force: bool = False,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    store = get_sync_run_store()
    enabled = store.get_auto_enabled()
    key = month_key(moment)
    try:
        active_keys = list_active_page_source_keys()
    except ValueError as exc:
        return _skipped(str(exc))

    rows = store.list_month(key)
    snapshots = _snapshots(rows, moment)
    decision = decide_monthly_run(
        now=moment,
        auto_enabled=enabled,
        runs=snapshots,
        all_source_keys=active_keys,
        force=force,
        scheduled=trigger == "schedule",
    )
    if decision.action == "skip":
        return _skipped(decision.reason, decision.attach_sync_id)

    if decision.supersede_run_id:
        try:
            cancel_rates_sync(decision.supersede_run_id)
        except ValueError:
            store.update_run(
                decision.supersede_run_id,
                {
                    "status": "failed",
                    "finished_at": moment.isoformat(),
                },
            )

    try:
        started = start_rates_sync(
            triggered_by=triggered_by,
            background_task_fn=background_task_fn,
            source_keys=list(decision.source_keys),
            month_key=key,
            trigger=trigger,
            forced=force,
        )
    except MonthRunBusy as exc:
        return _skipped("Une mise à jour du mois est déjà en cours.", exc.sync_id or None)

    status = get_rates_sync_status(started["sync_id"])
    return {
        "action": "started",
        "reason": decision.reason,
        "status": status["status"],
        **started,
    }


def run_scheduled_monthly_sync(*, force: bool = False, now: Optional[datetime] = None) -> int:
    """Lance le lot du mois et attend la fin. 0 si rien à faire, réussi ou partiel. 1 si tout a échoué."""

    def _inline(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)

    result = launch_monthly_sync(
        triggered_by="monthly-schedule",
        background_task_fn=_inline,
        trigger="schedule",
        force=force,
        now=now,
    )
    if result["action"] == "skip":
        logger.info("%s", result["reason"])
        return 0
    if result.get("status") == "failed":
        logger.error("Mise à jour du mois en échec (sync %s)", result.get("sync_id"))
        return 1
    logger.info(
        "Mise à jour du mois terminée : %s (sync %s)",
        result.get("status"),
        result.get("sync_id"),
    )
    return 0


def _skipped(reason: str, sync_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "action": "skip",
        "reason": reason,
        "sync_id": sync_id,
        "status": None,
        "jobs": [],
        "total": 0,
        "message": reason,
    }


def _snapshots(rows: List[Dict[str, Any]], now: datetime) -> List[StoredMonthlyRun]:
    repo = ScrapingRepository()
    snapshots: List[StoredMonthlyRun] = []
    for row in rows:
        succeeded: set[str] = set()
        for job in row.get("jobs") or []:
            source_key = job.get("source_key")
            if not source_key:
                continue
            if _job_succeeded(job):
                succeeded.add(source_key)
                continue
            job_id = job.get("job_id")
            if not job_id:
                continue
            try:
                live = repo.get_job(str(job_id))
            except Exception:
                live = None
            if live and live.get("status") == "completed" and live.get("success") is True:
                succeeded.add(source_key)
        snapshots.append(
            StoredMonthlyRun(
                id=str(row["id"]),
                status=str(row.get("status") or ""),
                started_at=_parse_started(row.get("started_at"), now),
                succeeded_source_keys=frozenset(succeeded),
            )
        )
    return snapshots


def _job_succeeded(job: Dict[str, Any]) -> bool:
    return job.get("status") == "completed" and job.get("success") is True


def _parse_started(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return fallback


def _latest_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    return max(rows, key=lambda row: str(row.get("started_at") or ""))
