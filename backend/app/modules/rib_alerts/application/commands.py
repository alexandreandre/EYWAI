"""
Commandes applicatives rib_alerts.

Logique déplacée depuis api/routers/rib_alerts (PATCH read, PATCH resolve). Comportement identique.
"""

from __future__ import annotations

from typing import Optional

from app.modules.rib_alerts.domain.rules import require_company_id
from app.modules.rib_alerts.infrastructure.repository import get_rib_alert_repository


def mark_rib_alert_read(
    alert_id: str,
    company_id: str | None,
) -> bool:
    """Marque une alerte comme lue. Lève MissingCompanyContextError si company_id absent. Retourne False si non trouvée."""
    company_id = require_company_id(company_id)
    repo = get_rib_alert_repository()
    return repo.mark_read(alert_id, company_id)


def resolve_rib_alert(
    alert_id: str,
    company_id: str | None,
    resolved_by: str,
    resolution_note: Optional[str] = None,
) -> bool:
    """Marque une alerte comme résolue. Lève MissingCompanyContextError si company_id absent. Retourne False si non trouvée."""
    company_id = require_company_id(company_id)
    repo = get_rib_alert_repository()
    return repo.resolve(alert_id, company_id, resolved_by, resolution_note)
