"""
Value objects du domaine schedules.

Cible : CalendrierPrevu, CalendrierReel, Periode (year, month), types de jour.
Placeholder minimal.
"""

from dataclasses import dataclass


@dataclass
class Periode:
    """Période (année, mois) pour un planning."""

    year: int
    month: int


@dataclass
class CalendrierJour:
    """Une entrée jour (placeholder pour calendrier prévu / réel)."""

    jour: int
    type: str
    heures_prevues: float | None = None
    heures_faites: float | None = None
