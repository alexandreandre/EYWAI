"""
DTOs applicatifs pour rib_alerts.

Structures pour liste paginée et filtres ; alignées sur l’API et le router legacy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RibAlertListFilters:
    """Filtres pour la liste des alertes (alignés sur les query params du GET legacy)."""

    is_read: Optional[bool] = None
    is_resolved: Optional[bool] = None
    alert_type: Optional[str] = None
    employee_id: Optional[str] = None
    limit: int = 50
    offset: int = 0


@dataclass
class RibAlertListResult:
    """Résultat de la query liste (alerts + total). Forme identique à la réponse GET legacy."""

    alerts: list[dict[str, Any]]
    total: int
