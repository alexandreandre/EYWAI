"""
Routers du module schedules : délégation à la couche application uniquement.

Aucune logique métier ni accès DB : validation (schémas), Depends, appel application,
conversion ScheduleAppError -> HTTPException, retour HTTP. Comportement identique aux anciens endpoints.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.core.security import get_current_user
from app.modules.schedules.application import ai_fill, commands, queries
from app.modules.schedules.application.badgeuse_import import (
    import_actual_hours_from_badgeuse,
    import_actual_hours_from_badgeuse_bulk,
)
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas import (
    ActualHoursRequest,
    AiCalendarProposalResponse,
    ApplyModelRequest,
    CalendarResponse,
    CumulsResponse,
    ImportBadgeuseBulkRequest,
    ImportBadgeuseEmployeeRequest,
    ParseInstructionRequest,
    PlannedCalendarRequest,
    RosterEmployee,
    TimesheetExtractJobResponse,
    TimesheetExtractProgress,
    TimesheetExtractStartResponse,
)
from app.modules.schedules.schemas.persist import (
    PersistTimesheetRequest,
    PersistTimesheetResponse,
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


@router.post("/actual-hours/import-badgeuse", status_code=200)
def import_actual_hours_from_badgeuse_route(
    employee_id: str,
    body: ImportBadgeuseEmployeeRequest,
    current_user: User = Depends(get_current_user),
):
    """Importe les heures effectives badgeuse dans le calendrier réel du mois."""
    _ = current_user
    try:
        result = import_actual_hours_from_badgeuse(
            employee_id,
            body.year,
            body.month,
            recalculate_payroll=body.recalculate_payroll,
        )
        return {
            "status": "success",
            "employee_id": result.employee_id,
            "year": result.year,
            "month": result.month,
            "days_updated": result.days_updated,
            "days_with_anomaly_warnings": result.days_with_anomaly_warnings,
            "warnings": result.warnings,
            "payroll_recalculated": result.payroll_recalculated,
        }
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


@router_rh.post("/import-badgeuse-actual-hours", status_code=200)
def import_badgeuse_actual_hours_bulk(
    request: ImportBadgeuseBulkRequest,
    current_user: User = Depends(get_current_user),
):
    """Importe les heures badgeuse vers le calendrier réel pour plusieurs employés."""
    _ = current_user
    try:
        return import_actual_hours_from_badgeuse_bulk(
            company_id=request.company_id,
            employee_ids=request.employee_ids,
            year=request.year,
            month=request.month,
            recalculate_payroll=request.recalculate_payroll,
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


_MAX_TIMESHEET_BYTES = 15 * 1024 * 1024  # 15 Mo


@router_rh.post(
    "/assisted-fill/parse-text", response_model=AiCalendarProposalResponse
)
def assisted_fill_parse_text(
    payload: ParseInstructionRequest,
    current_user: User = Depends(get_current_user),
):
    """Convertit une instruction en langage naturel en proposition d'heures réelles.

    Ne persiste rien : la proposition est revue par le RH avant enregistrement.
    """
    try:
        _ = current_user
        return ai_fill.parse_instruction(
            year=payload.year,
            month=payload.month,
            instruction=payload.instruction,
            roster=payload.employees,
            single_employee=payload.single_employee,
            broadcast=payload.broadcast,
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post(
    "/assisted-fill/extract-timesheet", response_model=AiCalendarProposalResponse
)
async def assisted_fill_extract_timesheet(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    employees: str = Form("[]"),
    single_employee: bool = Form(False),
    document_scope: str = Form("auto"),
    week_anchor_date: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Analyse un relevé de pointeuse (PDF/image) en proposition d'heures réelles.

    `employees` est une chaîne JSON [{id, first_name, last_name}] pour la
    résolution des noms. `single_employee` force l'attribution à l'unique
    employé du roster (mode fiche collaborateur). Ne persiste rien.

    `document_scope` : auto | weekly | monthly.
    `week_anchor_date` : date ISO (YYYY-MM-DD) de début de semaine si relevé ambigu.
    """
    from datetime import date as date_type

    _ = current_user
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Le fichier est vide.")
    if len(content) > _MAX_TIMESHEET_BYTES:
        raise HTTPException(
            status_code=400, detail="Fichier trop volumineux (max 15 Mo)."
        )
    try:
        raw_roster = json.loads(employees or "[]")
        roster = [RosterEmployee(**item) for item in raw_roster]
    except (json.JSONDecodeError, TypeError, ValueError):
        roster = []

    parsed_anchor: date_type | None = None
    if week_anchor_date and week_anchor_date.strip():
        try:
            parsed_anchor = date_type.fromisoformat(week_anchor_date.strip())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="week_anchor_date invalide (format attendu : YYYY-MM-DD).",
            ) from None

    scope = document_scope if document_scope in ("auto", "weekly", "monthly") else "auto"
    try:
        return ai_fill.extract_timesheet(
            year=year,
            month=month,
            file_content=content,
            filename=file.filename or "",
            roster=roster,
            single_employee=single_employee,
            document_scope=scope,
            week_anchor_date=parsed_anchor,
            company_id=current_user.active_company_id,
            user_id=current_user.id,
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post(
    "/assisted-fill/extract-timesheet/start",
    response_model=TimesheetExtractStartResponse,
)
async def assisted_fill_extract_timesheet_start(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    employees: str = Form("[]"),
    single_employee: bool = Form(False),
    document_scope: str = Form("auto"),
    week_anchor_date: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Lance l'extraction hybride IA en arrière-plan ; le front interroge GET /jobs/{id}."""
    from app.modules.schedules.application.timesheet_import_service import (
        create_import_job,
        run_timesheet_extraction_job,
    )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Le fichier est vide.")
    if len(content) > _MAX_TIMESHEET_BYTES:
        raise HTTPException(
            status_code=400, detail="Fichier trop volumineux (max 15 Mo)."
        )
    try:
        raw_roster = json.loads(employees or "[]")
        roster = [RosterEmployee(**item) for item in raw_roster]
    except (json.JSONDecodeError, TypeError, ValueError):
        roster = []

    scope = document_scope if document_scope in ("auto", "weekly", "monthly") else "auto"
    request_json = {
        "year": year,
        "month": month,
        "employees": [r.model_dump() for r in roster],
        "single_employee": single_employee,
        "document_scope": scope,
        "week_anchor_date": week_anchor_date.strip() if week_anchor_date else None,
    }

    try:
        job = create_import_job(
            company_id=str(current_user.active_company_id),
            user_id=str(current_user.id),
            filename=file.filename or "document.pdf",
            file_content=content,
            request_json=request_json,
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)

    job_id = str(job["id"])
    background_tasks.add_task(run_timesheet_extraction_job, job_id, content)

    return TimesheetExtractStartResponse(job_id=job_id, status="extracting")


@router_rh.get(
    "/assisted-fill/extract-timesheet/jobs/{job_id}",
    response_model=TimesheetExtractJobResponse,
)
async def assisted_fill_extract_timesheet_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Statut et proposition d'un job d'extraction de relevé."""
    from app.modules.schedules.application.timesheet_import_service import get_import_job

    job = get_import_job(job_id, company_id=str(current_user.active_company_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    progress_raw = job.get("progress_json") or {}
    progress = TimesheetExtractProgress(
        phase=str(progress_raw.get("phase") or job.get("status") or "queued"),
        pages_total=int(progress_raw.get("pages_total") or 0),
        pages_done=int(progress_raw.get("pages_done") or 0),
        current_page=int(progress_raw.get("current_page") or 0),
    )

    proposal = None
    if job.get("status") == "completed" and job.get("proposal_json"):
        proposal = AiCalendarProposalResponse.model_validate(job["proposal_json"])

    extraction_warnings: list[str] = []
    if proposal:
        extraction_warnings = list(proposal.extraction_warnings or [])

    return TimesheetExtractJobResponse(
        job_id=job_id,
        status=job.get("status") or "queued",
        progress=progress,
        proposal=proposal,
        error_message=job.get("error_message"),
        extraction_warnings=extraction_warnings,
    )


@router_rh.delete("/assisted-fill/extract-timesheet/jobs/{job_id}")
async def assisted_fill_cancel_extract_timesheet_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """Annulation best-effort d'un job en cours."""
    from app.modules.schedules.application.timesheet_import_service import cancel_import_job

    ok = cancel_import_job(job_id, company_id=str(current_user.active_company_id))
    if not ok:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    return {"status": "cancelled", "job_id": job_id}


@router_rh.post(
    "/assisted-fill/persist-timesheet", response_model=PersistTimesheetResponse
)
def assisted_fill_persist_timesheet(
    payload: PersistTimesheetRequest,
    current_user: User = Depends(get_current_user),
):
    """Enregistre en batch les jours proposés (merge prevu/réel par employé)."""
    from app.modules.schedules.application.persist_timesheet import (
        run_persist_timesheet_batch,
    )

    _ = current_user
    try:
        return run_persist_timesheet_batch(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ScheduleAppError as e:
        _handle_schedule_error(e)


__all__ = ["router", "router_me", "router_rh"]
