"""
Règles métier pures du domaine participation (Participation & Intéressement).

Aucune dépendance à FastAPI, DB ou infrastructure. Données en entrée : dicts/listes.
Comportement identique au routeur legacy (get_employee_participation_data).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

# Types de jour comptés comme présence lorsque heures_prevues > 0
PRESENCE_DAY_TYPES = frozenset(
    {
        "travail",
        "conge",
        "conge_paye",
        "rtt",
        "ferie",
        "fete",
    }
)

# Types de jour exclus (ne comptent jamais)
EXCLUDED_DAY_TYPES = frozenset(
    {
        "weekend",
        "maladie",
        "arret_maladie",
        "arret",
    }
)


def _day_counts_as_presence(
    day_type: str,
    heures_prevues: Any,
    heures_faites: Any,
) -> bool:
    """
    Indique si un jour compte comme présence selon les règles métier.
    - Si heures_faites > 0 : compte toujours.
    - Sinon si weekend ou maladie/arret : ne compte pas.
    - Sinon si heures_prevues > 0 et type dans travail/conge/rtt/ferie/fete : compte.
    """
    if heures_faites is not None and heures_faites > 0:
        return True
    if day_type in EXCLUDED_DAY_TYPES:
        return False
    if (
        heures_prevues is not None
        and heures_prevues > 0
        and day_type in PRESENCE_DAY_TYPES
    ):
        return True
    return False


def compute_presence_days_for_schedules(
    schedules: List[Dict[str, Any]],
) -> int:
    """
    Calcule le nombre de jours de présence pour un employé à partir de ses plannings.

    schedules : liste de dicts avec clés month, planned_calendar, actual_hours.
    - planned_calendar.calendrier_prevu : liste de jours (jour, type, heures_prevues).
    - actual_hours.calendrier_reel : liste de jours (jour, heures_faites).
    Dédoublonnage par (month, jour). Comportement identique au legacy.
    """
    total = 0
    counted: set = set()
    for schedule in schedules:
        if not isinstance(schedule, dict):
            continue
        month = schedule.get("month")
        planned_calendar = schedule.get("planned_calendar", {})
        actual_hours = schedule.get("actual_hours", {})
        planned_days = (
            planned_calendar.get("calendrier_prevu", [])
            if isinstance(planned_calendar, dict)
            else []
        )
        actual_days = (
            actual_hours.get("calendrier_reel", [])
            if isinstance(actual_hours, dict)
            else []
        )
        actual_by_day = {d.get("jour"): d for d in actual_days if isinstance(d, dict)}
        for planned_day in planned_days:
            if not isinstance(planned_day, dict):
                continue
            jour = planned_day.get("jour")
            day_type = planned_day.get("type", "")
            heures_prevues = planned_day.get("heures_prevues")
            actual_day = actual_by_day.get(jour, {})
            heures_faites = (
                actual_day.get("heures_faites")
                if isinstance(actual_day, dict)
                else None
            )
            day_key = f"{month}-{jour}"
            if day_key in counted:
                continue
            if _day_counts_as_presence(day_type, heures_prevues, heures_faites):
                total += 1
                counted.add(day_key)
        for actual_day in actual_days:
            if not isinstance(actual_day, dict):
                continue
            jour = actual_day.get("jour")
            heures_faites = actual_day.get("heures_faites")
            day_key = f"{month}-{jour}"
            if (
                heures_faites is not None
                and heures_faites > 0
                and day_key not in counted
            ):
                total += 1
                counted.add(day_key)
    return total


def compute_seniority_years(hire_date: date | str | None) -> int:
    """
    Calcule l'ancienneté en années (entier) à partir de la date d'embauche.
    Retourne 0 si hire_date est None ou invalide.
    """
    if hire_date is None:
        return 0
    try:
        if isinstance(hire_date, str):
            d = date.fromisoformat(hire_date)
        else:
            d = hire_date
        if not isinstance(d, date):
            return 0
        return max(0, (date.today() - d).days // 365)
    except (ValueError, TypeError):
        return 0


def extract_annual_salary_from_cumuls(cumuls: Any) -> float:
    """
    Extrait le brut total depuis une structure cumuls (employee_schedules ou payslip_data).
    cumuls peut être dict avec clé cumuls.cumuls.brut_total.
    Retourne 0.0 si structure invalide ou absente.
    """
    if not isinstance(cumuls, dict):
        return 0.0
    nested = cumuls.get("cumuls", {})
    if not isinstance(nested, dict):
        return 0.0
    brut = nested.get("brut_total", 0) or 0
    try:
        return float(brut)
    except (TypeError, ValueError):
        return 0.0
