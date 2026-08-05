"""Utilitaires partagés période d'essai (sans dépendance circulaire)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.modules.employees.domain.trial_period_dates import compute_trial_end

TRIAL_REMINDER_DAYS = 15


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value).strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def compute_trial_period_end(
    hire_date_raw: Any,
    periode_essai: Any,
) -> Optional[date]:
    """Fin de période d'essai à partir du jsonb historique.

    Conservée pour les lectures existantes ; le calcul lui-même vit dans
    trial_period_dates, partagé avec la table trial_periods.
    """
    hire = parse_date(hire_date_raw)
    if hire is None or not isinstance(periode_essai, dict):
        return None

    duree_raw = periode_essai.get("duree_initiale", periode_essai.get("duree"))
    try:
        duree = int(duree_raw)
    except (TypeError, ValueError):
        return None

    return compute_trial_end(hire, duree, str(periode_essai.get("unite") or "mois"))
