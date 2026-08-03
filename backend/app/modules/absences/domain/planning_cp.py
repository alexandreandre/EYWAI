"""Congés payés lus dans le calendrier de paie — domaine pur.

Les congés payés ne transitent pas par les demandes d'absence : ils sont saisis
jour par jour dans le planning. Ces fonctions les traduisent en demandes
validées équivalentes, pour que le moteur de soldes les décompte comme
n'importe quelle absence.
"""

from __future__ import annotations

from datetime import date
from typing import Any

PLANNING_CP_TYPE = "conges_payes"
PLANNING_CP_SOURCE = "planning"


def extract_planning_cp_days(planned_calendar: Any) -> list[str]:
    """Jours de congés payés d'un calendrier mensuel, en dates ISO triées."""
    if not isinstance(planned_calendar, dict):
        return []
    jours = planned_calendar.get("calendrier_prevu")
    if not isinstance(jours, list):
        return []
    periode = planned_calendar.get("periode") or {}
    annee = periode.get("annee")
    mois = periode.get("mois")
    if not isinstance(annee, int) or not isinstance(mois, int):
        return []

    days: list[str] = []
    for jour in jours:
        if not isinstance(jour, dict) or jour.get("type") != PLANNING_CP_TYPE:
            continue
        numero = jour.get("jour")
        if not isinstance(numero, int):
            continue
        try:
            days.append(date(annee, mois, numero).isoformat())
        except ValueError:
            # Jour hors du mois : calendrier incohérent, on l'ignore.
            continue
    return sorted(set(days))


def _existing_cp_days(validated: list[dict], employee_id: str) -> set[str]:
    taken: set[str] = set()
    for req in validated:
        if req.get("employee_id") != employee_id:
            continue
        if req.get("type") != "conge_paye" or req.get("status") != "validated":
            continue
        for day in req.get("selected_days") or []:
            if isinstance(day, str):
                taken.add(day[:10])
    return taken


def merge_planning_cp_days(
    validated: list[dict],
    planning_days_by_employee: dict[str, list[str]],
    cutoffs: dict[str, date | None],
) -> list[dict]:
    """
    Ajoute aux demandes validées les congés payés lus dans le planning.

    `cutoffs` porte, par salarié, la date de référence de la reprise de solde :
    les jours antérieurs ou égaux y sont déjà intégrés au solde d'ouverture et
    seraient sinon déduits une seconde fois.
    """
    result = list(validated)
    for employee_id, days in planning_days_by_employee.items():
        cutoff = cutoffs.get(employee_id)
        deja_pris = _existing_cp_days(validated, employee_id)
        retenus = sorted(
            {
                day[:10]
                for day in days
                if day[:10] not in deja_pris
                and (cutoff is None or date.fromisoformat(day[:10]) > cutoff)
            }
        )
        if not retenus:
            continue
        result.append(
            {
                "employee_id": employee_id,
                "type": "conge_paye",
                "status": "validated",
                "selected_days": retenus,
                "source": PLANNING_CP_SOURCE,
            }
        )
    return result
