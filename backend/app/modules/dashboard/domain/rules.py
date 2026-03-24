"""
Règles métier pures du module dashboard.

Aucune dépendance à la DB, FastAPI ou schémas. Entrées/sorties primitives ou dict/list.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Set


def count_working_days_between(start: date, end: date) -> int:
    """Nombre de jours ouvrés (lundi=0 à vendredi=4) entre start et end inclus."""
    if start > end:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def compute_absenteeism_rate(
    total_absence_days: int,
    theoretical_working_days: int,
) -> float:
    """
    Taux d'absentéisme = (jours d'absence / jours ouvrés théoriques) * 100.
    Arrondi à 1 décimale.
    """
    if theoretical_working_days <= 0:
        return 0.0
    return round((total_absence_days / theoretical_working_days) * 100, 1)


def get_previous_month(reference: date) -> tuple[int, int]:
    """Retourne (numéro_mois, année) du mois précédent par rapport à reference."""
    if reference.month == 1:
        return 12, reference.year - 1
    return reference.month - 1, reference.year


def get_last_n_past_months(
    month_numbers: Set[int],
    current_month: int,
    n: int = 12,
) -> List[int]:
    """
    Retourne les n derniers mois parmi month_numbers qui sont strictement
    antérieurs à current_month, triés par ordre chronologique.
    """
    past = [m for m in month_numbers if m < current_month]
    return sorted(past)[-n:]


def build_upcoming_events_raw(
    employees: List[Dict[str, Any]],
    reference_date: date,
    window_days: int,
) -> List[Dict[str, Any]]:
    """
    À partir d'une liste d'employés (dict avec date_naissance, hire_date, id, first_name, last_name),
    retourne les événements (anniversaire, ancienneté) dans la fenêtre [reference_date, reference_date + window_days].
    Chaque événement est un dict: id, type ('birthday'|'work_anniversary'), employee_name, date, detail.
    """
    end = reference_date + timedelta(days=window_days)
    events: List[Dict[str, Any]] = []

    for emp in employees:
        try:
            bday_str = emp.get("date_naissance")
            if bday_str:
                bday = date.fromisoformat(bday_str) if isinstance(bday_str, str) else bday_str
                bday_this_year = bday.replace(year=reference_date.year)
                bday_next_year = bday.replace(year=reference_date.year + 1)
                if (reference_date <= bday_this_year <= end) or (reference_date <= bday_next_year <= end):
                    age = reference_date.year - bday.year
                    events.append({
                        "id": f"bday-{emp['id']}",
                        "type": "birthday",
                        "employee_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
                        "date": bday_this_year,
                        "detail": f"fête ses {age} ans",
                    })

            hire_str = emp.get("hire_date")
            if hire_str:
                hire_date = date.fromisoformat(hire_str) if isinstance(hire_str, str) else hire_str
                hire_anniversary_this_year = hire_date.replace(year=reference_date.year)
                hire_anniversary_next_year = hire_date.replace(year=reference_date.year + 1)
                if (
                    reference_date <= hire_anniversary_this_year <= end
                    and hire_date.year < reference_date.year
                ) or (
                    reference_date <= hire_anniversary_next_year <= end
                    and hire_date.year < (reference_date.year + 1)
                ):
                    years = reference_date.year - hire_date.year
                    if years > 0:
                        events.append({
                            "id": f"work-{emp['id']}",
                            "type": "work_anniversary",
                            "employee_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
                            "date": hire_anniversary_this_year,
                            "detail": f"fête ses {years} an(s) d'ancienneté",
                        })
        except (ValueError, TypeError, KeyError):
            continue

    events.sort(key=lambda e: e["date"])
    return events


def aggregate_contract_distribution(employees: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compte par type de contrat (contract_type). Clé par défaut 'Non défini' si absent."""
    dist: Dict[str, int] = {}
    for emp in employees:
        ctype = emp.get("contract_type") or "Non défini"
        dist[ctype] = dist.get(ctype, 0) + 1
    return dist


def count_absence_days_in_range(
    absences: List[Dict[str, Any]],
    employee_ids: Set[str],
    start: date,
    end: date,
) -> int:
    """
    Compte le nombre de jours d'absence (selected_days) qui tombent dans [start, end]
    et sont des jours ouvrés, pour les employés dont l'id est dans employee_ids.
    """
    total = 0
    for absence in absences:
        if absence.get("employee_id") not in employee_ids:
            continue
        for day_str in absence.get("selected_days") or []:
            try:
                d = date.fromisoformat(day_str) if isinstance(day_str, str) else day_str
                if start <= d <= end and d.weekday() < 5:
                    total += 1
            except (ValueError, TypeError):
                continue
    return total
