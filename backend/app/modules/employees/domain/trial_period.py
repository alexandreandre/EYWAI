"""Règles pures : statut calculé de la période d'essai, pour affichage RH."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_bareme import DEFAULT_ALERT_DAYS
from app.modules.employees.domain.trial_period_shared import parse_date

TRIAL_STATUS_IN_PROGRESS = "in_progress"
TRIAL_STATUS_ENDING_SOON = "ending_soon"
TRIAL_STATUS_ENDED = "ended"
TRIAL_STATUS_CONFIRMED = "confirmed"
TRIAL_STATUS_TO_COMPLETE = "to_complete"

RECENT_HIRE_DAYS_FOR_TO_COMPLETE = 90

_TRACKED_EMPLOYMENT_STATUSES = frozenset({"actif", "en_onboarding"})


def _empty_enrichment() -> Dict[str, Any]:
    return {
        "trial_period_applicable": False,
        "trial_period_status": None,
        "trial_period_end_date": None,
        "trial_period_days_remaining": None,
        "trial_period_renewal_possible": None,
    }


def calculate_trial_period_status(
    hire_date_raw: Any,
    trial_period: Any,
    employment_status: Any,
    reference_date: Optional[date] = None,
    alert_days: int = DEFAULT_ALERT_DAYS,
) -> Dict[str, Any]:
    """Statut enrichi de la période d'essai, à partir de la ligne trial_periods.

    Returns:
        dict avec trial_period_applicable, trial_period_status,
        trial_period_end_date, trial_period_days_remaining,
        trial_period_renewal_possible.
    """
    ref = reference_date or date.today()
    status_norm = str(employment_status or "actif").strip().lower()

    if status_norm not in _TRACKED_EMPLOYMENT_STATUSES:
        return _empty_enrichment()

    if not isinstance(trial_period, dict):
        # Sans période enregistrée, seule une embauche récente mérite d'être
        # signalée : au-delà, il n'y a plus rien à compléter.
        hire = parse_date(hire_date_raw)
        if hire is not None and (ref - hire).days <= RECENT_HIRE_DAYS_FOR_TO_COMPLETE:
            return {
                "trial_period_applicable": True,
                "trial_period_status": TRIAL_STATUS_TO_COMPLETE,
                "trial_period_end_date": None,
                "trial_period_days_remaining": None,
                "trial_period_renewal_possible": None,
            }
        return _empty_enrichment()

    db_status = str(trial_period.get("status") or "")
    end = parse_date(trial_period.get("end_date"))
    renewal = trial_period.get("renewal_allowed")
    if renewal is not None:
        renewal = bool(renewal)

    if db_status == "confirmee":
        return {
            "trial_period_applicable": True,
            "trial_period_status": TRIAL_STATUS_CONFIRMED,
            "trial_period_end_date": end.isoformat() if end else None,
            "trial_period_days_remaining": None,
            "trial_period_renewal_possible": renewal,
        }

    # Une période rompue a produit une sortie : elle ne se suit plus ici.
    if db_status != "en_cours" or end is None:
        return _empty_enrichment()

    days_remaining = (end - ref).days
    if days_remaining < 0:
        status = TRIAL_STATUS_ENDED
    elif days_remaining <= alert_days:
        status = TRIAL_STATUS_ENDING_SOON
    else:
        status = TRIAL_STATUS_IN_PROGRESS

    return {
        "trial_period_applicable": True,
        "trial_period_status": status,
        "trial_period_end_date": end.isoformat(),
        "trial_period_days_remaining": days_remaining,
        "trial_period_renewal_possible": renewal,
    }


__all__ = [
    "TRIAL_STATUS_CONFIRMED",
    "TRIAL_STATUS_ENDED",
    "TRIAL_STATUS_ENDING_SOON",
    "TRIAL_STATUS_IN_PROGRESS",
    "TRIAL_STATUS_TO_COMPLETE",
    "calculate_trial_period_status",
]
