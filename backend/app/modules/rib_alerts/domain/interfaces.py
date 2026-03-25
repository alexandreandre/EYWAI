"""
Ports (interfaces) pour le module rib_alerts.

L’infrastructure implémente ces interfaces ; l’application ne dépend que des abstractions.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from app.modules.rib_alerts.domain.entities import RibAlert


class IRibAlertRepository(Protocol):
    """Accès persistance aux alertes RIB (table rib_alerts)."""

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
        """Liste les alertes avec filtres ; retourne (items, total count)."""
        ...

    def get_by_id(self, alert_id: str, company_id: str) -> Optional[RibAlert]:
        """Retourne une alerte par id si elle appartient à la company."""
        ...

    def mark_read(self, alert_id: str, company_id: str) -> bool:
        """Marque l’alerte comme lue ; retourne True si mise à jour."""
        ...

    def resolve(
        self,
        alert_id: str,
        company_id: str,
        resolved_by: str,
        resolution_note: Optional[str] = None,
    ) -> bool:
        """Marque l’alerte comme résolue ; retourne True si mise à jour."""
        ...

    def create(self, payload: dict[str, Any]) -> Optional[RibAlert]:
        """Crée une alerte (usage interne : on_rib_updated / on_rib_submitted)."""
        ...
