"""Calcul de la fin de période d'essai.

Le décompte va de quantième à quantième et la période expire la veille du
quantième correspondant : deux mois à compter du 1er mars s'achèvent le
30 avril à minuit. Quand ce quantième n'existe pas dans le mois d'arrivée
(31 janvier + 1 mois), la période court jusqu'au dernier jour du mois.

Une rupture notifiée après cette date est prononcée hors période d'essai,
donc requalifiée : le jour compte.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta

UNIT_DAYS = "jours"
UNIT_WEEKS = "semaines"
UNIT_MONTHS = "mois"

VALID_UNITS = frozenset({UNIT_DAYS, UNIT_WEEKS, UNIT_MONTHS})


def _normalize_unit(unit: object) -> Optional[str]:
    raw = str(unit or "").strip().lower()
    if raw.startswith("jour"):
        return UNIT_DAYS
    if raw.startswith("sem"):
        return UNIT_WEEKS
    if raw.startswith("mois"):
        return UNIT_MONTHS
    return None


def _last_day_of_period(start: date, value: int, unit: str) -> date:
    """Dernier jour inclus d'une période de `value` `unit` commençant à `start`."""
    if unit == UNIT_DAYS:
        return start + timedelta(days=value - 1)
    if unit == UNIT_WEEKS:
        return start + timedelta(weeks=value) - timedelta(days=1)

    target = start + relativedelta(months=value)
    if target.day == start.day:
        # Le quantième existe : la période expire la veille.
        return target - timedelta(days=1)
    # relativedelta a tronqué au dernier jour du mois (31 janvier + 1 mois
    # donne le 28 février) : c'est déjà le dernier jour de la période.
    return target


def compute_trial_end(
    start: date,
    duration_value: int,
    duration_unit: str,
    renewal_value: Optional[int] = None,
    renewal_unit: Optional[str] = None,
) -> Optional[date]:
    """Dernier jour de la période d'essai, renouvellement inclus.

    Retourne None si la durée ou l'unité sont inexploitables.
    """
    unit = _normalize_unit(duration_unit)
    if unit is None:
        return None
    try:
        value = int(duration_value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None

    end = _last_day_of_period(start, value, unit)

    if renewal_value is None:
        return end

    r_unit = _normalize_unit(renewal_unit) or unit
    try:
        r_value = int(renewal_value)
    except (TypeError, ValueError):
        return end
    if r_value <= 0:
        return end

    # Le renouvellement repart le lendemain de la fin initiale.
    return _last_day_of_period(end + timedelta(days=1), r_value, r_unit)


__all__ = [
    "UNIT_DAYS",
    "UNIT_WEEKS",
    "UNIT_MONTHS",
    "VALID_UNITS",
    "compute_trial_end",
]
