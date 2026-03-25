# app/modules/cse/domain/rules.py
"""
Règles métier CSE pures — sans I/O, sans FastAPI.
"""

from datetime import date
from typing import Literal, Optional


def validate_mandate_dates(start_date: date, end_date: date) -> None:
    """Lève ValueError si end_date < start_date."""
    if end_date < start_date:
        raise ValueError("La date de fin doit être après la date de début")


def election_alert_level(
    days_remaining: int,
) -> Optional[Literal["info", "warning", "critical"]]:
    """
    Niveau d'alerte électorale selon les jours restants avant fin de mandat.
    Comportement identique au calcul actuel (J-180, J-90, J-30).
    Retourne None si > 180 jours (pas d'alerte).
    """
    if days_remaining <= 0:
        return "critical"
    if days_remaining <= 30:
        return "critical"
    if days_remaining <= 90:
        return "warning"
    if days_remaining <= 180:
        return "info"
    return None


def election_alert_message(days_remaining: int) -> str:
    """Message d'alerte électorale (comportement identique à l'existant)."""
    if days_remaining <= 0:
        return "Le mandat se termine aujourd'hui ou est déjà terminé"
    return f"Le mandat se termine dans {days_remaining} jours"
