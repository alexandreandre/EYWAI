"""
Enums du domaine super_admin.

Préparation migration : statuts et types utilisés par le module.
"""
from enum import Enum


class SystemHealthStatus(str, Enum):
    """Statut retourné par GET /system/health."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
