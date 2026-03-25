"""
Entités du domaine schedules.

Cible de migration : agrégat « planning employé / mois » (employee_id, year, month,
planned_calendar, actual_hours, cumuls, payroll_events). Pour l’instant placeholder.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EmployeeScheduleMonth:
    """
    Planning d’un employé pour un mois donné (cible).
    Correspond à une ligne de la table employee_schedules.
    """

    employee_id: str
    company_id: str
    year: int
    month: int
    planned_calendar: Optional[Dict[str, Any]] = None
    actual_hours: Optional[Dict[str, Any]] = None
    payroll_events: Optional[Dict[str, Any]] = None
    cumuls: Optional[Dict[str, Any]] = None

    # Placeholder : à enrichir lors de la migration
    def to_storage(self) -> Dict[str, Any]:
        """Sérialisation pour persistance (placeholder)."""
        return {}
