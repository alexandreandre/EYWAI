"""Période d'essai posée à l'embauche.

Le barème société propose une durée ; une saisie explicite du formulaire la
remplace. C'est ici que le barème, jusqu'alors codé en dur dans le formulaire
React, devient une décision serveur.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.employees.domain.trial_period_bareme import resolve_trial_proposal
from app.modules.employees.domain.trial_period_shared import parse_date
from app.modules.trial_periods.application.commands import contract_duration_months


def _normalize_unit(value: Any, default: str) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("jour"):
        return "jours"
    if raw.startswith("sem"):
        return "semaines"
    if raw.startswith("mois"):
        return "mois"
    return default


def plan_trial_period(
    employee: Dict[str, Any],
    company_settings: Any,
    requested: Optional[Dict[str, Any]],
    wanted: bool = True,
) -> Optional[Dict[str, Any]]:
    """Paramètres de la période à créer, ou None s'il n'y en a pas.

    `requested` est la saisie du formulaire (durée, unité, renouvellement) ;
    `wanted` à False traduit une case décochée, qui prime sur tout.
    """
    if not wanted:
        return None

    start = parse_date(employee.get("hire_date"))
    if start is None:
        return None

    proposal = resolve_trial_proposal(
        company_settings,
        str(employee.get("contract_type") or ""),
        str(employee.get("statut") or ""),
        contract_duration_months(employee),
    )

    if isinstance(requested, dict) and requested:
        duree_raw = requested.get("duree_initiale", requested.get("duree"))
        try:
            duree = int(duree_raw)
        except (TypeError, ValueError):
            duree = 0
        if duree > 0:
            default_unit = proposal.duration_unit if proposal else "mois"
            default_renewal = proposal.renewal_allowed if proposal else False
            return {
                "start_date": start,
                "duration_value": duree,
                "duration_unit": _normalize_unit(requested.get("unite"), default_unit),
                "renewal_allowed": bool(
                    requested.get("renouvellement_possible", default_renewal)
                ),
            }

    if proposal is None:
        return None

    return {
        "start_date": start,
        "duration_value": proposal.duration_value,
        "duration_unit": proposal.duration_unit,
        "renewal_allowed": proposal.renewal_allowed,
    }


__all__ = ["plan_trial_period"]
