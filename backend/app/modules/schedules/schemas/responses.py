"""
Schémas Pydantic sortie API du module schedules.

Définitions canoniques : calendrier (planned/actual), cumuls.
Comportement identique à l’ancien schemas/schedule.py.
"""

from typing import List

from pydantic import BaseModel


# ----- GET /calendar-data -----


class CalendarData(BaseModel):
    day: int
    type: str
    hours: float | None = None


class CalendarResponse(BaseModel):
    planned: List[CalendarData]
    actual: List[CalendarData]


# ----- GET /api/me/current-cumuls -----


class CumulsPeriode(BaseModel):
    annee_en_cours: int | None = None
    dernier_mois_calcule: int | None = None


class CumulsValues(BaseModel):
    brut_total: float | None = None
    net_imposable: float | None = None
    impot_preleve_a_la_source: float | None = None
    heures_remunerees: float | None = None
    heures_supplementaires_remunerees: float | None = None
    reduction_generale_patronale: float | None = None


class CumulsResponse(BaseModel):
    periode: CumulsPeriode | None = None
    cumuls: CumulsValues | None = None


__all__ = [
    "CalendarData",
    "CalendarResponse",
    "CumulsPeriode",
    "CumulsResponse",
    "CumulsValues",
]
