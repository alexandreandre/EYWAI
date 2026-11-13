"""Saisie d'un mois sur sa révision lue, réservée jusqu'aux effets et au calcul."""

from typing import Any

from app.modules.payroll.documents.verrou_generation import (
    GenerationDejaEnCours,
    GenerationVerrouIndisponible,
    verrou_de_generation,
)
from app.modules.schedules.application import commands, queries
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.infrastructure.calendar_edit_repository import (
    calendar_edit,
    read_snapshot,
)
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
    extract_calendrier_reel_from_actual_hours,
)
from app.modules.schedules.schemas.requests import (
    ActualHoursRequest,
    CalendarSaveRequest,
    PlannedCalendarRequest,
)


def get_snapshot(employee_id: str, company_id: str, year: int, month: int) -> dict[str, Any]:
    raw = read_snapshot(employee_id, company_id, year, month)
    planned = extract_calendrier_prevu_from_planned_calendar(raw["planned_calendar"])
    actual = extract_calendrier_reel_from_actual_hours(raw["actual_hours"])
    return {
        "year": year, "month": month, "revision": raw["revision"], "busy": raw["busy"],
        "calendrier_prevu": planned, "calendrier_reel": actual,
        "jours_en_conflit": queries._jours_en_conflit_du_mois(employee_id, year, month, actual, planned=planned),
    }


def save_calendar(employee_id: str, company_id: str, payload: CalendarSaveRequest) -> dict[str, Any]:
    try:
        # Prendre le verrou du bulletin AVANT celui des entrées : une
        # génération déjà engagée ne rencontre pas une réservation temporaire
        # de son calendrier alors que cette saisie va être refusée.
        with verrou_de_generation(employee_id, payload.year, payload.month, required=True):
            return _save_reserved_calendar(employee_id, company_id, payload)
    except (GenerationDejaEnCours, GenerationVerrouIndisponible) as exc:
        busy = isinstance(exc, GenerationDejaEnCours)
        code = "calendar_busy" if busy else "calendar_unavailable"
        message = (
            "Une saisie ou un calcul est en cours pour ce salarié et ce mois. Vos saisies restent affichées ; réessayez après son achèvement."
            if busy else "La réservation du bulletin est indisponible. Vos saisies restent affichées ; réessayez dans un instant."
        )
        raise ScheduleAppError(code, message, 409 if busy else 503, {"code": code, "message": message}) from exc


def _save_reserved_calendar(employee_id: str, company_id: str, payload: CalendarSaveRequest) -> dict[str, Any]:
    with calendar_edit(employee_id, company_id, payload.year, payload.month, str(payload.expected_revision) if payload.expected_revision else None) as lease:
        warnings: list[dict[str, Any]] = []
        stage = "planned"
        confirmed: list[str] = []
        try:
            if payload.calendrier_prevu is not None:
                lease.ensure_alive()
                result = commands.update_planned_calendar(employee_id, PlannedCalendarRequest(
                    year=payload.year, month=payload.month, calendrier_prevu=payload.calendrier_prevu,
                ))
                warnings = result.get("warnings", [])
                confirmed.append("planned")
            stage = "actual"
            if payload.calendrier_reel is not None:
                lease.ensure_alive()
                commands.update_actual_hours(employee_id, ActualHoursRequest(
                    year=payload.year, month=payload.month, calendrier_reel=payload.calendrier_reel,
                ))
                confirmed.append("actual")
            stage = "payroll"
            if payload.recalculate_payroll:
                lease.ensure_alive()
                commands.calculate_payroll_events(employee_id, payload.year, payload.month)
                confirmed.append("payroll")
            stage = "confirmation"
            lease.ensure_alive()
            snapshot = get_snapshot(employee_id, company_id, payload.year, payload.month)
            lease.ensure_alive()
            if not snapshot["revision"] or snapshot["busy"]:
                raise RuntimeError("Réservation ou révision finale non confirmée")
            return {
                **snapshot,
                "warnings": warnings, "payroll_recalculated": payload.recalculate_payroll,
            }
        except Exception as exc:
            # Des commandes HTTP ont pu être confirmées avant l'échec : aucune
            # prétention à un rollback global, aucun succès ou retry aveugle.
            message = "L’enregistrement n’a pas pu être confirmé entièrement. Vos saisies restent affichées ; conservez-les avant de recharger le calendrier."
            raise ScheduleAppError("calendar_save_failed", message, 503, {
                "code": "calendar_save_failed", "message": message,
                "stage": stage, "confirmed": confirmed,
            }) from exc
