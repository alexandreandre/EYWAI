"""
Entité domaine : alerte RIB.

Alignée sur la table rib_alerts et le contrat API actuel (api/routers/rib_alerts, frontend ribAlerts.ts).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=False)
class RibAlert:
    """Alerte RIB (modification ou doublon)."""

    id: Optional[str]
    company_id: str
    employee_id: Optional[str]
    alert_type: str  # rib_modified | rib_duplicate
    severity: str  # info | warning | error
    title: str
    message: str
    details: dict[
        str, Any
    ]  # old_iban_masked, new_iban_masked, iban_masked, duplicate_employees
    is_read: bool
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    resolved_by: Optional[str] = None
    created_at: Optional[datetime] = None
