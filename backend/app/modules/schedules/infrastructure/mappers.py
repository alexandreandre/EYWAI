"""
Mappers entre lignes DB (employee_schedules) et structures utilisées par l'application.

Extraction planned_calendar / actual_hours / cumuls depuis une ligne ou response.data.
"""

from typing import Any, Dict, List, Optional


def row_to_planned_calendar(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extrait planned_calendar depuis une ligne employee_schedules."""
    if not row or not row.get("planned_calendar"):
        return None
    return row["planned_calendar"]


def row_to_actual_hours(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extrait actual_hours depuis une ligne employee_schedules."""
    if not row or not row.get("actual_hours"):
        return None
    return row["actual_hours"]


def row_to_cumuls(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extrait cumuls depuis une ligne employee_schedules."""
    if not row or not row.get("cumuls"):
        return None
    return row["cumuls"]


def extract_calendrier_prevu_from_planned_calendar(
    planned_calendar: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Retourne la liste calendrier_prevu depuis l'objet planned_calendar."""
    if not planned_calendar:
        return []
    return planned_calendar.get("calendrier_prevu", [])


def extract_calendrier_reel_from_actual_hours(
    actual_hours: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Retourne la liste calendrier_reel depuis l'objet actual_hours."""
    if not actual_hours:
        return []
    return actual_hours.get("calendrier_reel", [])
