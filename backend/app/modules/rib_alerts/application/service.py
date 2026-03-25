"""
Service applicatif rib_alerts.

Facade optionnelle : expose les commandes et queries pour injection unique si besoin.
La logique métier est dans commands et queries ; le router peut les appeler directement.
"""

from __future__ import annotations

from typing import Optional

from app.modules.rib_alerts.application.commands import (
    mark_rib_alert_read,
    resolve_rib_alert,
)
from app.modules.rib_alerts.application.dto import (
    RibAlertListFilters,
    RibAlertListResult,
)
from app.modules.rib_alerts.application.queries import get_rib_alerts


def list_rib_alerts(
    company_id: str, filters: RibAlertListFilters
) -> RibAlertListResult:
    """Liste les alertes RIB. Délègue à get_rib_alerts."""
    return get_rib_alerts(company_id, filters)


def mark_read(alert_id: str, company_id: str) -> bool:
    """Marque une alerte comme lue. Délègue à mark_rib_alert_read."""
    return mark_rib_alert_read(alert_id, company_id)


def resolve(
    alert_id: str,
    company_id: str,
    resolved_by: str,
    resolution_note: Optional[str] = None,
) -> bool:
    """Marque une alerte comme résolue. Délègue à resolve_rib_alert."""
    return resolve_rib_alert(alert_id, company_id, resolved_by, resolution_note)
