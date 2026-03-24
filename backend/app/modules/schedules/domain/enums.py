"""
Enums du domaine schedules.

Cible : types de jour pour apply-model (work, rest, holiday, travail, weekend,
conge, ferie, arret_maladie). Placeholder pour évolution.
"""
from enum import StrEnum


class DayType(StrEnum):
    """Type de jour dans un modèle de planning (apply-model)."""
    WORK = "work"
    TRAVAIL = "travail"
    REST = "rest"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    CONGE = "conge"
    FERIE = "ferie"
    ARRET_MALADIE = "arret_maladie"
