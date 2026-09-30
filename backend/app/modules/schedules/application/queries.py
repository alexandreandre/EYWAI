"""
Queries (cas d'usage lecture) du module schedules.

Délèguent au repository et aux providers (infrastructure). Comportement identique.
Lève ScheduleAppError pour not_found / erreurs ; le router convertira en HTTPException.
"""
from app.core.logging import get_logger, log_app_debug

logger = get_logger("modules.schedules.application.queries")

from datetime import date
from typing import Any, Dict, List
import calendar as _calendar

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.domain.exceptions import ScheduleNotFoundError
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
    extract_calendrier_reel_from_actual_hours,
    row_to_cumuls,
)
from app.modules.schedules.domain.conflits_arret import (
    arrets_necessaires,
    jours_en_conflit,
)
from app.modules.schedules.infrastructure.arrets_valides import arrets_valides_reader
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
        logger.exception("Exception")
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
        log_app_debug(logger, f'DEBUG (planned): planned_calendar={planned_calendar}')

        calendrier_prevu = extract_calendrier_prevu_from_planned_calendar(
            planned_calendar
        )
        if planned_calendar is None:
            log_app_debug(logger, 'Calendrier prévu absent en base — retour vide.')
        return {"year": year, "month": month, "calendrier_prevu": calendrier_prevu}
    except Exception as e:
        logger.exception("Exception")
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e


def _jours_en_conflit_du_mois(
    employee_id: str, year: int, month: int, calendrier_reel: List[Dict[str, Any]]
) -> List[int]:
    """Jours du mois où des heures sont saisies alors que le prévu est un arrêt
    ou une absence (règle de `conflits_arret`, la même que la garde de génération).

    Lecture d'écran : si le planning ou les arrêts ne se lisent pas, on ne bloque
    pas l'affichage. Sans les arrêts, seul le type prévu juge (un week-end
    d'arrêt n'est alors pas marqué) ; la génération, elle, exige les arrêts.
    """
    try:
        if not any(float(e.get("heures_faites") or 0) > 0 for e in calendrier_reel):
            return []
        prevu = [
            {**e, "annee": year, "mois": month}
            for e in extract_calendrier_prevu_from_planned_calendar(
                schedule_repository.get_planned_calendar(employee_id, year, month)
            )
            if isinstance(e, dict)
        ]
        reel = [{**e, "annee": year, "mois": month} for e in calendrier_reel]
        arrets: List[Dict[str, Any]] = []
        if arrets_necessaires(prevu, reel):
            try:
                arrets = arrets_valides_reader.par_salarie(
                    [employee_id],
                    date(year, month, 1),
                    date(year, month, _calendar.monthrange(year, month)[1]),
                ).get(str(employee_id), [])
            except Exception as exc:  # noqa: BLE001 — lecture d'écran tolérante
                logger.warning(
                    "[calendrier] Arrêts validés illisibles pour %s : %s", employee_id, exc
                )
        return [c.jour for c in jours_en_conflit(prevu, reel, arrets)]
    except Exception:  # noqa: BLE001 — le marquage ne doit jamais casser la lecture
        logger.exception("[calendrier] Jours en conflit non calculés pour %s", employee_id)
        return []


def get_actual_hours(employee_id: str, year: int, month: int) -> Dict[str, Any]:
    """
    Récupère les heures réelles depuis employee_schedules.
    Retourne {"year": int, "month": int, "calendrier_reel": [...]}.
    """
    try:
        actual_hours = schedule_repository.get_actual_hours(employee_id, year, month)
        log_app_debug(logger, f'DEBUG (actual): actual_hours={actual_hours}')

        calendrier_reel = extract_calendrier_reel_from_actual_hours(actual_hours)
        if actual_hours is None:
            log_app_debug(logger, 'Calendrier réel absent en base — retour vide.')
        return {"year": year, "month": month, "calendrier_reel": calendrier_reel}
    except Exception as e:
        logger.exception("Exception")
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e


def get_actual_hours_du_calendrier(
    employee_id: str, year: int, month: int
) -> Dict[str, Any]:
    """Heures réelles lues par le calendrier (GET `/actual-hours`), avec
    `jours_en_conflit`. Le prévu et les arrêts ne sont lus que pour cet écran :
    l'import des pointages appelle `get_actual_hours` sans ce coût.
    """
    lecture = get_actual_hours(employee_id, year, month)
    return {
        **lecture,
        "jours_en_conflit": _jours_en_conflit_du_mois(
            employee_id, year, month, lecture["calendrier_reel"]
        ),
    }


def get_my_current_cumuls(employee_id: str) -> CumulsResponse:
    """
    Récupère les derniers cumuls pour l'employé (order year desc, month desc, limit 1).
    Retourne CumulsResponse(periode=None, cumuls=None) si aucun cumul.
    """
    try:
        log_app_debug(logger, f'DEBUG [get_my_current_cumuls]: Récupération cumuls pour ID: {employee_id}')

        row = schedule_repository.get_latest_cumuls_row(employee_id)
        cumuls_data = row_to_cumuls(row)

        if row and cumuls_data is not None:
            log_app_debug(logger, 'DEBUG [get_my_current_cumuls]: Cumuls trouvés.')
            if isinstance(cumuls_data, dict):
                return CumulsResponse(**cumuls_data)
            log_app_debug(logger, f"WARN [get_my_current_cumuls]: 'cumuls' data is not a dict for ID: {employee_id}")
            return CumulsResponse(periode=None, cumuls=None)

        log_app_debug(logger, f'WARN [get_my_current_cumuls]: Aucun cumul trouvé pour ID: {employee_id}')
        return CumulsResponse(periode=None, cumuls=None)

    except Exception as e:
        logger.warning(f'ERROR [get_my_current_cumuls]: Exception pour ID {employee_id}:')
        logger.exception("Exception")
        raise ScheduleAppError(
            "error", f"Erreur interne: {str(e)}", status_code=500
        ) from e
