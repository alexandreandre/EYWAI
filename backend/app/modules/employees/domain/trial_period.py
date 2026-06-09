"""Règles pures : statut calculé de la période d'essai."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_shared import (
    TRIAL_REMINDER_DAYS,
    compute_trial_period_end,
    parse_date,
)

TRIAL_STATUS_IN_PROGRESS = "in_progress"
TRIAL_STATUS_ENDING_SOON = "ending_soon"
TRIAL_STATUS_ENDED = "ended"
TRIAL_STATUS_CONFIRMED = "confirmed"
TRIAL_STATUS_TO_COMPLETE = "to_complete"

TRIAL_JSON_STATUT_CONFIRMED = "confirmee"
TRIAL_JSON_STATUT_EN_COURS = "en_cours"

RECENT_HIRE_DAYS_FOR_TO_COMPLETE = 90

_TRACKED_EMPLOYMENT_STATUSES = frozenset({"actif", "en_onboarding"})


def _is_trial_confirmed(periode_essai: Any) -> bool:
    if not isinstance(periode_essai, dict):
        return False
    statut = str(periode_essai.get("statut") or "").strip().lower()
    return statut == TRIAL_JSON_STATUT_CONFIRMED


def _renewal_possible(periode_essai: Any) -> Optional[bool]:
    if not isinstance(periode_essai, dict):
        return None
    if "renouvellement_possible" not in periode_essai:
        return None
    return bool(periode_essai.get("renouvellement_possible"))


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
    periode_essai: Any,
    employment_status: Any,
    contract_type: Any = None,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calcule le statut enrichi de la période d'essai pour affichage RH / alertes.

    Returns:
        dict avec trial_period_applicable, trial_period_status, trial_period_end_date,
        trial_period_days_remaining, trial_period_renewal_possible.
    """
    ref = reference_date or date.today()
    status_norm = str(employment_status or "actif").strip().lower()

    if status_norm not in _TRACKED_EMPLOYMENT_STATUSES:
        return _empty_enrichment()

    if _is_trial_confirmed(periode_essai):
        end = compute_trial_period_end(hire_date_raw, periode_essai)
        return {
            "trial_period_applicable": True,
            "trial_period_status": TRIAL_STATUS_CONFIRMED,
            "trial_period_end_date": end.isoformat() if end else None,
            "trial_period_days_remaining": None,
            "trial_period_renewal_possible": _renewal_possible(periode_essai),
        }

    end = compute_trial_period_end(hire_date_raw, periode_essai)
    if end is None:
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

    days_remaining = (end - ref).days
    renewal = _renewal_possible(periode_essai)

    if days_remaining < 0:
        status = TRIAL_STATUS_ENDED
    elif days_remaining <= TRIAL_REMINDER_DAYS:
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


def is_trial_eligible_for_reminder(periode_essai: Any) -> bool:
    """True si la période d'essai doit déclencher une relance (non confirmée)."""
    if not isinstance(periode_essai, dict):
        return False
    return not _is_trial_confirmed(periode_essai)


__all__ = [
    "TRIAL_STATUS_CONFIRMED",
    "TRIAL_STATUS_ENDED",
    "TRIAL_STATUS_ENDING_SOON",
    "TRIAL_STATUS_IN_PROGRESS",
    "TRIAL_STATUS_TO_COMPLETE",
    "TRIAL_JSON_STATUT_CONFIRMED",
    "TRIAL_JSON_STATUT_EN_COURS",
    "calculate_trial_period_status",
    "is_trial_eligible_for_reminder",
]
