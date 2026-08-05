"""Jointure de la période d'essai active sur une ligne salarié.

Supabase remonte une relation inverse sous forme de liste. Un salarié peut
avoir plusieurs périodes — une réembauche crée la sienne — mais une seule est
active, et c'est celle qui intéresse l'affichage comme les relances.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.modules.trial_periods.domain.constants import STATUS_EN_COURS

# Projection complète, pour la fiche salarié.
TRIAL_PERIOD_JOIN = (
    "trial_period:trial_periods(id, start_date, end_date, status, "
    "duration_value, duration_unit, renewal_allowed, renewed_at, "
    "renewal_duration_value, renewal_duration_unit, confirmed_at)"
)

# Projection réduite, pour les compteurs et les relances.
TRIAL_PERIOD_JOIN_LIGHT = "trial_period:trial_periods(end_date, status)"


def normalize_trial_period(row: Dict[str, Any]) -> Dict[str, Any]:
    """Remplace la liste jointe par la seule période active, ou None."""
    trials = row.get("trial_period")
    if isinstance(trials, list):
        active = [t for t in trials if t.get("status") == STATUS_EN_COURS]
        if not active:
            # Aucune période active : on garde la plus récemment terminée pour
            # que la fiche puisse afficher « embauche confirmée ».
            closed = sorted(trials, key=lambda t: str(t.get("end_date") or ""))
            row["trial_period"] = closed[-1] if closed else None
        else:
            row["trial_period"] = active[0]
    return row


def normalize_trial_periods(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_trial_period(row) for row in rows]


__all__ = [
    "TRIAL_PERIOD_JOIN",
    "TRIAL_PERIOD_JOIN_LIGHT",
    "normalize_trial_period",
    "normalize_trial_periods",
]
