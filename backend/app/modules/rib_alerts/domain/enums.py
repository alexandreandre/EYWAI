"""
Énumérations du domaine rib_alerts.

Alignées sur l’existant : alert_type (rib_modified | rib_duplicate), severity (info | warning | error).
"""

from __future__ import annotations

from enum import StrEnum


class RibAlertType(StrEnum):
    """Type d’alerte RIB."""

    RIB_MODIFIED = "rib_modified"
    RIB_DUPLICATE = "rib_duplicate"


class RibAlertSeverity(StrEnum):
    """Sévérité de l’alerte."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
