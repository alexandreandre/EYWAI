"""
Queries (cas d'usage lecture) du module schedules.

Délèguent au repository et aux providers (infrastructure). Comportement identique.
Lève ScheduleAppError pour not_found / erreurs ; le router convertira en HTTPException.
"""

import traceback
from typing import Any, Dict, List

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.exceptions import ScheduleNotFoundError
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
    extract_calendrier_reel_from_actual_hours,
    row_to_cumuls,
)
from app.modules.schedules.infrastructure.providers import file_calendar_provider
from app.modules.schedules.infrastructure.queries import employee_company_reader
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.modules.schedules.schemas.responses import CumulsResponse


def get_employee_calendar(
    employee_id: str, year: int, month: int
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Récupère les heures prévues et réelles depuis les fichiers du moteur de paie.
    Retourne {"planned": [...], "actual": [...]}.
    """
    try:
        folder_name = employee_company_reader.get_employee_folder_name(employee_id)
        planned_data = file_calendar_provider.read_planned_calendar(
            folder_name, year, month
        )
        actual_data = file_calendar_provider.read_actual_hours(folder_name, year, month)
        return {"planned": planned_data, "actual": actual_data}
    except ScheduleNotFoundError as e:
        raise ScheduleAppError("not_found", str(e), status_code=404) from e
    except Exception as e:
        traceback.print_exc()
        raise ScheduleAppError("error", str(e), status_code=500) from e


def get_planned_calendar(employee_id: str, year: int, month: int) -> Dict[str, Any]:
    """
    Récupère le calendrier prévu depuis employee_schedules.
    Retourne {"year": int, "month": int, "calendrier_prevu": [...]}.
    """
    try:
        planned_calendar = schedule_repository.get_planned_calendar(
            employee_id, year, month
        )
        print(f"DEBUG (planned): planned_calendar={planned_calendar}")

        calendrier_prevu = extract_calendrier_prevu_from_planned_calendar(
            planned_calendar
        )
        if planned_calendar is None:
            print(
                "AVERTISSEMENT (planned): La réponse de Supabase est None. On retourne un calendrier vide."
            )
        return {"year": year, "month": month, "calendrier_prevu": calendrier_prevu}
    except Exception as e:
        traceback.print_exc()
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e


def get_actual_hours(employee_id: str, year: int, month: int) -> Dict[str, Any]:
    """
    Récupère les heures réelles depuis employee_schedules.
    Retourne {"year": int, "month": int, "calendrier_reel": [...]}.
    """
    try:
        actual_hours = schedule_repository.get_actual_hours(employee_id, year, month)
        print(f"DEBUG (actual): actual_hours={actual_hours}")

        calendrier_reel = extract_calendrier_reel_from_actual_hours(actual_hours)
        if actual_hours is None:
            print(
                "AVERTISSEMENT (actual): La réponse de Supabase est None. On retourne un calendrier vide."
            )
        return {"year": year, "month": month, "calendrier_reel": calendrier_reel}
    except Exception as e:
        traceback.print_exc()
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e


def get_my_current_cumuls(employee_id: str) -> CumulsResponse:
    """
    Récupère les derniers cumuls pour l'employé (order year desc, month desc, limit 1).
    Retourne CumulsResponse(periode=None, cumuls=None) si aucun cumul.
    """
    try:
        print(
            f"DEBUG [get_my_current_cumuls]: Récupération cumuls pour ID: {employee_id}"
        )

        row = schedule_repository.get_latest_cumuls_row(employee_id)
        cumuls_data = row_to_cumuls(row)

        if row and cumuls_data is not None:
            print("DEBUG [get_my_current_cumuls]: Cumuls trouvés.")
            if isinstance(cumuls_data, dict):
                return CumulsResponse(**cumuls_data)
            print(
                f"WARN [get_my_current_cumuls]: 'cumuls' data is not a dict for ID: {employee_id}"
            )
            return CumulsResponse(periode=None, cumuls=None)

        print(
            f"WARN [get_my_current_cumuls]: Aucun cumul trouvé pour ID: {employee_id}"
        )
        return CumulsResponse(periode=None, cumuls=None)

    except Exception as e:
        print(f"ERROR [get_my_current_cumuls]: Exception pour ID {employee_id}:")
        traceback.print_exc()
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e
