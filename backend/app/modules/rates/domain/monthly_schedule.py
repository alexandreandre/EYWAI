"""Décision de la mise à jour mensuelle des taux.

Le mois et la fenêtre se calculent en heure de Paris. Le navigateur ne décide pas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional, Sequence
from zoneinfo import ZoneInfo

from app.modules.rates.domain.rate_source_mapping import normalize_source_key

PARIS = ZoneInfo("Europe/Paris")
CATCHUP_LAST_DAY = 3
STALE_RUNNING = timedelta(hours=3)

_MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


@dataclass(frozen=True)
class StoredMonthlyRun:
    id: str
    status: str
    started_at: datetime
    succeeded_source_keys: frozenset[str]


@dataclass(frozen=True)
class MonthlyDecision:
    action: Literal["skip", "start"]
    reason: str
    source_keys: tuple[str, ...] = ()
    supersede_run_id: Optional[str] = None
    attach_sync_id: Optional[str] = None


def month_key(now: datetime) -> str:
    paris = _as_paris(now)
    return f"{paris.year:04d}-{paris.month:02d}"


def in_catchup_window(now: datetime) -> bool:
    return _as_paris(now).day <= CATCHUP_LAST_DAY


def decide_monthly_run(
    *,
    now: datetime,
    auto_enabled: bool,
    runs: Sequence[StoredMonthlyRun],
    all_source_keys: Sequence[str],
    force: bool = False,
    scheduled: bool = False,
) -> MonthlyDecision:
    """Choisit de lancer, de s'arrêter, ou de remplacer un run trop vieux."""
    if not all_source_keys:
        return MonthlyDecision("skip", "Aucune source active trouvée pour cette mise à jour.")

    if not auto_enabled and not force:
        return MonthlyDecision("skip", "Mise à jour automatique désactivée.")

    if scheduled and not force and not in_catchup_window(now):
        return MonthlyDecision(
            "skip",
            "Hors de la fenêtre automatique (du 1er au 3 du mois).",
        )

    fresh_running = [
        run
        for run in runs
        if run.status == "running" and now - _aware(run.started_at) < STALE_RUNNING
    ]
    stale_running = [
        run
        for run in runs
        if run.status == "running" and now - _aware(run.started_at) >= STALE_RUNNING
    ]

    if fresh_running and not force:
        current = _most_recent(fresh_running)
        return MonthlyDecision(
            "skip",
            "Une mise à jour du mois est déjà en cours.",
            attach_sync_id=current.id,
        )

    supersede: Optional[str] = None
    if fresh_running and force:
        supersede = _most_recent(fresh_running).id
    elif stale_running:
        supersede = _most_recent(stale_running).id

    if force:
        keys = tuple(all_source_keys)
    else:
        done = _succeeded_keys(runs)
        keys = tuple(
            key
            for key in all_source_keys
            if normalize_source_key(key) not in done
        )

    if not keys:
        done_run = _latest_finished_success(runs)
        return MonthlyDecision(
            "skip",
            "Mise à jour du mois déjà effectuée.",
            attach_sync_id=done_run.id if done_run else None,
        )

    return MonthlyDecision(
        "start",
        "Lancement de la mise à jour du mois.",
        source_keys=keys,
        supersede_run_id=supersede,
    )


def describe_monthly_status(
    now: datetime,
    *,
    enabled: bool,
    runs: Sequence[StoredMonthlyRun],
) -> str:
    if not enabled:
        return "Mise à jour automatique désactivée."

    latest = _latest(runs)
    if latest and latest.status == "running" and now - _aware(latest.started_at) < STALE_RUNNING:
        return "Mise à jour du mois en cours."
    if latest and latest.status == "succeeded":
        return "Mise à jour du mois effectuée."
    if latest and latest.status == "partial":
        return (
            "Mise à jour partielle : certaines sources n'ont pas abouti. "
            "Les autres taux sont à jour."
        )
    if latest and latest.status == "failed":
        # Le 3, le cron du lendemain ne tourne plus : ne pas promettre un essai.
        if in_catchup_window(now) and _as_paris(now).day < CATCHUP_LAST_DAY:
            return "La mise à jour du mois a échoué. Un nouvel essai automatique est prévu demain matin."
        return "La mise à jour du mois n'a pas abouti."
    if latest and latest.status == "cancelled":
        return "Mise à jour du mois interrompue."
    if in_catchup_window(now):
        return "Mise à jour du mois pas encore lancée."
    return f"Prochaine exécution automatique : {_next_first_label(now)}."


def panel_actions(
    now: datetime,
    *,
    enabled: bool,
    runs: Sequence[StoredMonthlyRun],
) -> tuple[bool, bool]:
    """(afficher Lancer / Réessayer, afficher Recommencer)."""
    if not enabled:
        return False, False
    latest = _latest(runs)
    if latest and latest.status == "running" and now - _aware(latest.started_at) < STALE_RUNNING:
        return False, False
    if latest and latest.status == "partial":
        return True, True
    if latest and latest.status == "succeeded":
        return False, True
    return True, False


def run_button_label(runs: Sequence[StoredMonthlyRun]) -> str:
    latest = _latest(runs)
    if latest and latest.status == "partial":
        return "Réessayer les sources en échec"
    return "Lancer la mise à jour du mois"


def _succeeded_keys(runs: Sequence[StoredMonthlyRun]) -> set[str]:
    done: set[str] = set()
    for run in runs:
        if run.status == "cancelled":
            continue
        done.update(normalize_source_key(key) for key in run.succeeded_source_keys)
    return done


def _latest_finished_success(runs: Sequence[StoredMonthlyRun]) -> Optional[StoredMonthlyRun]:
    finished = [run for run in runs if run.status in ("succeeded", "partial")]
    if not finished:
        return None
    return _most_recent(finished)


def _latest(runs: Sequence[StoredMonthlyRun]) -> Optional[StoredMonthlyRun]:
    if not runs:
        return None
    return _most_recent(runs)


def _most_recent(runs: Sequence[StoredMonthlyRun]) -> StoredMonthlyRun:
    return max(runs, key=lambda run: _aware(run.started_at))


def _as_paris(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    return now.astimezone(PARIS)


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment


def _next_first_label(now: datetime) -> str:
    paris = _as_paris(now)
    year = paris.year + (1 if paris.month == 12 else 0)
    month = 1 if paris.month == 12 else paris.month + 1
    return f"1er {_MOIS[month - 1]} {year}"
