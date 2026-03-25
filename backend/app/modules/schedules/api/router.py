"""
Routers du module schedules : délégation à la couche application uniquement.

Aucune logique métier ni accès DB : validation (schémas), Depends, appel application,
conversion ScheduleAppError -> HTTPException, retour HTTP. Comportement identique aux anciens endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.schedules.application import commands, queries
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas import (
    ActualHoursRequest,
    ApplyModelRequest,
    CalendarResponse,
    CumulsResponse,
    PlannedCalendarRequest,
)
from app.modules.users.schemas.responses import User


def _handle_schedule_error(e: ScheduleAppError) -> None:
    """Convertit ScheduleAppError en HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.message)


# ----- Router 1 : /api/employees/{employee_id} -----

router = APIRouter(
    prefix="/api/employees/{employee_id}",
    tags=["Schedules & Calendars"],
)


@router.get("/calendar-data", response_model=CalendarResponse)
def get_employee_calendar(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère les heures prévues et réelles pour le calendrier d'un salarié."""
    try:
        _ = current_user
        return queries.get_employee_calendar(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.get("/planned-calendar", response_model=PlannedCalendarRequest)
def get_planned_calendar(employee_id: str, year: int, month: int):
    """Récupère le calendrier prévu depuis la table employee_schedules."""
    try:
        return queries.get_planned_calendar(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/planned-calendar", status_code=200)
def update_planned_calendar(employee_id: str, payload: PlannedCalendarRequest):
    """Met à jour (ou crée) le calendrier prévu dans la table employee_schedules."""
    try:
        return commands.update_planned_calendar(employee_id, payload)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.get("/actual-hours", response_model=ActualHoursRequest)
def get_actual_hours(employee_id: str, year: int, month: int):
    """Récupère les heures réelles depuis la table employee_schedules."""
    try:
        return queries.get_actual_hours(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/actual-hours", status_code=200)
def update_actual_hours(employee_id: str, payload: ActualHoursRequest):
    """Met à jour (ou crée) les heures réelles dans la table employee_schedules."""
    try:
        return commands.update_actual_hours(employee_id, payload)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/calculate-payroll-events", status_code=200)
def calculate_payroll_events(employee_id: str, request_body: dict):
    """Déclenche le calcul des événements de paie pour un employé sur une période donnée."""
    try:
        if not isinstance(request_body, dict):
            raise HTTPException(
                status_code=422,
                detail="Body invalide: un objet JSON est attendu",
            )
        year_value = request_body.get("year")
        month_value = request_body.get("month")
        if year_value is None or month_value is None:
            raise HTTPException(
                status_code=422,
                detail="Body invalide: 'year' et 'month' sont obligatoires",
            )
        year = int(year_value)
        month = int(month_value)
        return commands.calculate_payroll_events(employee_id, year, month)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=422,
            detail=f"Body invalide: {str(e)}",
        ) from e
    except ScheduleAppError as e:
        _handle_schedule_error(e)


# ----- Router 2 : /api/me -----

router_me = APIRouter(
    prefix="/api/me",
    tags=["My Schedules & Data (Employee View)"],
)


@router_me.get("/current-cumuls", response_model=CumulsResponse)
def get_my_current_cumuls(current_user: User = Depends(get_current_user)):
    """Récupère les derniers cumuls annuels calculés pour l'employé connecté."""
    try:
        employee_id = current_user.id
        return queries.get_my_current_cumuls(employee_id)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


# ----- Router 3 : /api/schedules (RH) -----

router_rh = APIRouter(
    prefix="/api/schedules",
    tags=["RH - Schedule Management"],
)


@router_rh.post("/apply-model")
async def apply_schedule_model(
    request: ApplyModelRequest,
    current_user: User = Depends(get_current_user),
):
    """Applique un modèle de planning à plusieurs employés pour un mois donné. Réservé aux RH."""
    try:
        return commands.apply_schedule_model(request, current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


__all__ = ["router", "router_me", "router_rh"]
