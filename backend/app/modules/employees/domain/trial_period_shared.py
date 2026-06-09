"""Utilitaires partagés période d'essai (sans dépendance circulaire)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from dateutil.relativedelta import relativedelta

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
    hire = parse_date(hire_date_raw)
    if hire is None or not isinstance(periode_essai, dict):
        return None

    duree_raw = periode_essai.get("duree_initiale", periode_essai.get("duree"))
    try:
        duree = int(duree_raw)
    except (TypeError, ValueError):
        return None
    if duree <= 0:
        return None

    unite = str(periode_essai.get("unite") or "mois").lower()
    if unite.startswith("jour"):
        return hire + timedelta(days=duree)
    if unite.startswith("sem"):
        return hire + timedelta(days=duree * 7)
    return hire + relativedelta(months=duree)
