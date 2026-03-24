"""
Schémas Pydantic entrée API du module schedules.

Définitions canoniques : calendrier prévu/réel, apply-model.
Comportement identique à l’ancien schemas/schedule.py et api/routers/schedules.py.
"""
from typing import Dict, List, Literal

from pydantic import BaseModel


# ----- Calendrier prévu (GET/POST /planned-calendar) -----


class PlannedCalendarEntry(BaseModel):
    """
    Entrée du calendrier prévu pour un jour.

    Note sur heures_prevues :
    - Pour forfait jour : 1 = jour travaillé, 0/null = jour non travaillé
    - Pour non forfait jour : nombre d'heures (ex: 8, 7.5)
    Le forfait jour est déterminé par employees.statut (contient "forfait jour").
    """
    jour: int
    type: str
    heures_prevues: float | None = None


class PlannedCalendarRequest(BaseModel):
    year: int
    month: int
    calendrier_prevu: List[PlannedCalendarEntry]


# ----- Heures réelles (GET/POST /actual-hours) -----


class ActualHoursEntry(BaseModel):
    jour: int
    heures_faites: float | None = None
    type: str | None = None


class ActualHoursRequest(BaseModel):
    year: int
    month: int
    calendrier_reel: List[ActualHoursEntry]


# ----- Apply-model (POST /api/schedules/apply-model) -----


class DayConfigModel(BaseModel):
    """Configuration d'un jour pour apply-model (work, rest, holiday, etc.)."""
    type: Literal[
        "work", "rest", "holiday", "travail", "weekend", "conge", "ferie", "arret_maladie"
    ]
    hours: float


class WeekConfigModel(BaseModel):
    """Configuration d'une semaine (lundi à dimanche)."""
    monday: DayConfigModel
    tuesday: DayConfigModel
    wednesday: DayConfigModel
    thursday: DayConfigModel
    friday: DayConfigModel
    saturday: DayConfigModel
    sunday: DayConfigModel


class ApplyModelRequest(BaseModel):
    """Body POST /api/schedules/apply-model : appliquer un modèle à plusieurs employés."""
    employee_ids: List[str]
    year: int
    month: int
    week_configs: Dict[int, WeekConfigModel]  # 1-5 : configuration de chaque semaine du mois


__all__ = [
    "ActualHoursEntry",
    "ActualHoursRequest",
    "ApplyModelRequest",
    "DayConfigModel",
    "PlannedCalendarEntry",
    "PlannedCalendarRequest",
    "WeekConfigModel",
]
