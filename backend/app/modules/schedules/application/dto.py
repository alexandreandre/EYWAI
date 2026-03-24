"""
DTOs (objets de transfert) applicatifs du module schedules.

Cible : structures passées entre api et application (ex. CalendrierPrevuDto,
CalendrierReelDto, CumulsDto). Pour l’instant placeholder minimal.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PlannedCalendarDto:
    """DTO entrée/sortie calendrier prévu (placeholder)."""
    year: int
    month: int
    calendrier_prevu: List[Dict[str, Any]]


@dataclass
class ActualHoursDto:
    """DTO entrée/sortie heures réelles (placeholder)."""
    year: int
    month: int
    calendrier_reel: List[Dict[str, Any]]


@dataclass
class CumulsDto:
    """DTO sortie cumuls (placeholder)."""
    periode: Optional[Dict[str, Any]] = None
    cumuls: Optional[Dict[str, Any]] = None
