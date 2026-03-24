"""
Repository rib_alerts : orchestration des requêtes et mappers.

Délègue les accès DB à infrastructure/queries.py ; utilise les mappers pour entités.
Comportement strictement identique au legacy.
"""
from __future__ import annotations

from typing import Any, Optional

from app.modules.rib_alerts.domain.entities import RibAlert
from app.modules.rib_alerts.domain.interfaces import IRibAlertRepository
from app.modules.rib_alerts.infrastructure.mappers import row_to_rib_alert
from app.modules.rib_alerts.infrastructure.queries import (
    get_rib_alert_row_by_id,
    insert_rib_alert,
    list_rib_alerts_rows,
    update_rib_alert_read,
    update_rib_alert_resolve,
)


class SupabaseRibAlertRepository:
    """Implémentation Supabase de IRibAlertRepository. Utilise queries + mappers."""

    def list(
        self,
        company_id: str,
        *,
        is_read: Optional[bool] = None,
        is_resolved: Optional[bool] = None,
        alert_type: Optional[str] = None,
        employee_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RibAlert], int]:
        data, total = list_rib_alerts_rows(
            company_id,
            is_read=is_read,
            is_resolved=is_resolved,
            alert_type=alert_type,
            employee_id=employee_id,
            limit=limit,
            offset=offset,
        )
        return ([row_to_rib_alert(row) for row in data], total)

    def get_by_id(self, alert_id: str, company_id: str) -> Optional[RibAlert]:
        row = get_rib_alert_row_by_id(alert_id, company_id)
        return row_to_rib_alert(row) if row is not None else None

    def mark_read(self, alert_id: str, company_id: str) -> bool:
        return update_rib_alert_read(alert_id, company_id)

    def resolve(
        self,
        alert_id: str,
        company_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
    ) -> bool:
        return update_rib_alert_resolve(alert_id, company_id, resolved_by, resolution_note)

    def create(self, payload: dict[str, Any]) -> Optional[RibAlert]:
        row = insert_rib_alert(payload)
        return row_to_rib_alert(row) if row is not None else None


_repository_instance: Optional[SupabaseRibAlertRepository] = None


def get_rib_alert_repository() -> IRibAlertRepository:
    """Retourne l’instance du repository (singleton pour cohérence)."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = SupabaseRibAlertRepository()
    return _repository_instance
