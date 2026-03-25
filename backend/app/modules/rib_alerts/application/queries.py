"""
Queries applicatives rib_alerts.

Logique déplacée depuis api/routers/rib_alerts (GET liste). Comportement identique.
"""

from __future__ import annotations

from app.modules.rib_alerts.application.dto import (
    RibAlertListFilters,
    RibAlertListResult,
)
from app.modules.rib_alerts.domain.rules import require_company_id
from app.modules.rib_alerts.infrastructure.mappers import rib_alert_to_response_dict
from app.modules.rib_alerts.infrastructure.repository import get_rib_alert_repository


def get_rib_alerts(
    company_id: str | None,
    filters: RibAlertListFilters,
) -> RibAlertListResult:
    """Liste les alertes RIB avec filtres et pagination. Lève MissingCompanyContextError si company_id absent."""
    company_id = require_company_id(company_id)
    repo = get_rib_alert_repository()
    alerts, total = repo.list(
        company_id,
        is_read=filters.is_read,
        is_resolved=filters.is_resolved,
        alert_type=filters.alert_type,
        employee_id=filters.employee_id,
        limit=filters.limit,
        offset=filters.offset,
    )
    return RibAlertListResult(
        alerts=[rib_alert_to_response_dict(a) for a in alerts],
        total=total,
    )
