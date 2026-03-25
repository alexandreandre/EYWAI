"""
Value objects du domaine absences.

Types de jour calendrier, soldes par type, etc. — à enrichir lors de la migration.
"""

from dataclasses import dataclass
from typing import Union

# Placeholder : types pour remaining (float ou littéral affiché).
RemainingDisplay = Union[float, str]  # float | "N/A" | "selon événement"


@dataclass
class AbsenceBalanceValue:
    """Solde pour un type d'absence (CP, RTT, repos, événement familial, sans solde)."""

    type: str
    acquired: float
    taken: float
    remaining: RemainingDisplay


@dataclass
class CalendarDayValue:
    """Un jour dans le calendrier planifié (employee_schedules.planned_calendar)."""

    jour: int
    type: str  # "travail" | "conge" | "rtt" | ...
    heures_prevues: float = 0.0
