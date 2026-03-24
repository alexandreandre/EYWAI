"""
Service d'orchestration du module schedules.

Logique partagée : récupération company_id/statut via IEmployeeCompanyReader,
délégation aux règles du domain (normalisation forfait jour). Pas d'accès DB direct.
"""
from typing import Any, Dict, List, Tuple

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain import rules as domain_rules
from app.modules.schedules.domain.exceptions import (
    ScheduleDatabaseError,
    ScheduleNotFoundError,
)
from app.modules.schedules.infrastructure.queries import employee_company_reader


def get_employee_company_and_statut(employee_id: str) -> Tuple[str, str | None]:
    """
    Récupère company_id et statut pour un employé.
    Lève ScheduleAppError si employé absent ou sans company_id.
    """
    try:
        return employee_company_reader.get_company_and_statut(employee_id)
    except ScheduleNotFoundError as e:
        raise ScheduleAppError(
            "not_found",
            str(e),
            status_code=404,
        ) from e
    except ScheduleDatabaseError as e:
        raise ScheduleAppError(
            "database_error",
            str(e),
            status_code=500,
        ) from e


def normalize_planned_calendar_for_employee(
    calendrier_prevu: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """Délègue à domain.rules.normalize_planned_calendar_for_forfait_jour."""
    return domain_rules.normalize_planned_calendar_for_forfait_jour(
        calendrier_prevu, employee_statut
    )


def normalize_actual_hours_for_employee(
    calendrier_reel: List[Dict[str, Any]], employee_statut: str | None
) -> List[Dict[str, Any]]:
    """Délègue à domain.rules.normalize_actual_hours_for_forfait_jour."""
    return domain_rules.normalize_actual_hours_for_forfait_jour(
        calendrier_reel, employee_statut
    )
