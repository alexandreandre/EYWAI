"""
Règles métier pures — migrées depuis api/routers/absences.py.

Aucun accès DB : toutes les données passent en paramètres.
"""
import math
from datetime import date

from app.modules.absences.domain.enums import SALARY_CERTIFICATE_ABSENCE_TYPES


def calculate_acquired_cp(hire_date: date, today: date) -> float:
    """
    Jours de congés payés acquis (période 1er juin N-1 → 31 mai N, 2.5 j/mois, arrondi supérieur).
    """
    if today.month < 6:
        period_start = date(today.year - 2, 6, 1)
        period_end = date(today.year - 1, 5, 31)
    else:
        period_start = date(today.year - 1, 6, 1)
        period_end = date(today.year, 5, 31)

    if hire_date > period_end:
        return 0.0

    start_of_calculation = max(hire_date, period_start)
    months_worked = (
        (period_end.year - start_of_calculation.year) * 12
        + (period_end.month - start_of_calculation.month)
        + 1
    )
    acquired_days = months_worked * 2.5
    return float(math.ceil(acquired_days))


def calculate_acquired_rtt(
    hire_date: date, today: date, rtt_annual_base: float = 10.0
) -> float:
    """
    RTT acquis pour l'année (prorata si embauche en cours d'année).
    Compte les mois travaillés depuis l'embauche jusqu'à aujourd'hui (même année).
    FIXME: rtt_annual_base depuis config entreprise.
    """
    if hire_date.year < today.year:
        return rtt_annual_base
    # Mois travaillés depuis l'embauche jusqu'à aujourd'hui (inclus)
    months_worked_this_year = (
        (today.year - hire_date.year) * 12 + (today.month - hire_date.month) + 1
    )
    acquired_rtt = (rtt_annual_base / 12) * months_worked_this_year
    return round(acquired_rtt, 2)


def requires_salary_certificate(absence_type: str) -> bool:
    """True si le type d'absence déclenche une attestation de salaire."""
    return absence_type in SALARY_CERTIFICATE_ABSENCE_TYPES
