"""
Enums du domaine dashboard.
"""
from enum import Enum


class TeamPulseEventType(str, Enum):
    """Type d'événement team pulse (anniversaire, ancienneté)."""
    BIRTHDAY = "birthday"
    WORK_ANNIVERSARY = "work_anniversary"
