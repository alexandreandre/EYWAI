"""
Routers du module schedules : délégation à la couche application uniquement.

Aucune logique métier ni accès DB : validation (schémas), Depends, appel application,
conversion ScheduleAppError -> HTTPException, retour HTTP. Comportement identique aux anciens endpoints.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.schedules.application import ai_fill, commands, plan_commands, queries
from app.modules.schedules.application.badgeuse_import import (
    import_actual_hours_from_badgeuse,
    import_actual_hours_from_badgeuse_bulk,
)
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas import (
    ActualHoursRequest,
    AiCalendarProposalResponse,
    ApplyModelRequest,
    ApplyPresetRequest,
    CalendarResponse,
    CumulsResponse,
    GenerateCalendarRequest,
    SchedulePlanUpsert,
    ImportBadgeuseBulkRequest,
    ImportBadgeuseEmployeeRequest,
    ParseInstructionRequest,
    PlannedCalendarRequest,
    PlannedCalendarResponse,
    RosterEmployee,
    TimesheetExtractJobResponse,
    TimesheetExtractProgress,
    TimesheetExtractStartResponse,
)
from app.modules.schedules.schemas.persist import (
    PersistTimesheetRequest,
    PersistTimesheetResponse,
)
from app.modules.schedules.schemas.timesheet_import import (
    TimesheetImportCommitRequest,
    TimesheetImportProfileUpdate,
)
from app.modules.schedules.schemas.punch_accounting import (
    PunchAccountingSettingsUpdate,
    PunchOvertimeReviewUpdate,
    PunchShiftSlotCreate,
    PunchShiftSlotUpdate,
)
from app.modules.users.schemas.responses import User


def _handle_schedule_error(e: ScheduleAppError) -> None:
    """Convertit ScheduleAppError en HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=e.message)


def _require_employee_schedule_access(
    current_user: User, employee_id: str, permission_code: str
) -> None:
    company_id = str(current_user.active_company_id or "")
    if not company_id:
        raise HTTPException(status_code=400, detail="Entreprise active requise.")
    access_control_service.require_employee_access(
        current_user, company_id, permission_code, employee_id
    )


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
        _require_employee_schedule_access(current_user, employee_id, "schedules.view_all")
        return queries.get_employee_calendar(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.get("/planned-calendar", response_model=PlannedCalendarResponse)
def get_planned_calendar(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère le calendrier prévu depuis la table employee_schedules."""
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.view_all")
        return queries.get_planned_calendar(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/planned-calendar", status_code=200)
def update_planned_calendar(
    employee_id: str,
    payload: PlannedCalendarRequest,
    current_user: User = Depends(get_current_user),
):
    """Met à jour (ou crée) le calendrier prévu dans la table employee_schedules."""
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.update")
        return commands.update_planned_calendar(employee_id, payload)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.get("/actual-hours", response_model=ActualHoursRequest)
def get_actual_hours(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Récupère les heures réelles depuis la table employee_schedules."""
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.view_all")
        return queries.get_actual_hours(employee_id, year, month)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/actual-hours", status_code=200)
def update_actual_hours(
    employee_id: str,
    payload: ActualHoursRequest,
    current_user: User = Depends(get_current_user),
):
    """Met à jour (ou crée) les heures réelles dans la table employee_schedules."""
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.update")
        return commands.update_actual_hours(employee_id, payload)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router.post("/calculate-payroll-events", status_code=200)
def calculate_payroll_events(
    employee_id: str,
    request_body: dict,
    current_user: User = Depends(get_current_user),
):
    """Déclenche le calcul des événements de paie pour un employé sur une période donnée."""
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.update")
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
    try:
        _require_employee_schedule_access(current_user, employee_id, "schedules.update")
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

def _exiger_profil_rh(current_user: User = Depends(get_current_user)) -> User:
    """Droit RH dans la société active — garde de TOUT le routeur RH.

    Ce routeur portait « RH » dans son nom et ses tags, mais ses routes ne
    vérifiaient que l'authentification : n'importe quel salarié listait les
    heures supplémentaires nominatives de ses collègues, approuvait les
    SIENNES (donc se les faisait payer) et pouvait désactiver l'exigence de
    validation manager pour toute la société (audit du 23/08/2026).
    """
    if current_user.is_platform_admin:
        return current_user
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=403, detail="Impossible de déterminer l'entreprise."
        )
    if not current_user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")
    return current_user


router_rh = APIRouter(
    prefix="/api/schedules",
    tags=["RH - Schedule Management"],
    dependencies=[Depends(_exiger_profil_rh)],
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


# ----- Plans de calendriers horaires + presets 2026 (RH) -----


@router_rh.get("/plans")
def list_schedule_plans(current_user: User = Depends(get_current_user)):
    """Liste les plans de calendriers horaires de l'entreprise active."""
    try:
        return plan_commands.list_plans(current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/plans", status_code=201)
def create_schedule_plan(
    payload: SchedulePlanUpsert, current_user: User = Depends(get_current_user)
):
    try:
        return plan_commands.create_plan(payload, current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.put("/plans/{plan_id}")
def update_schedule_plan(
    plan_id: str,
    payload: SchedulePlanUpsert,
    current_user: User = Depends(get_current_user),
):
    try:
        return plan_commands.update_plan(plan_id, payload, current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.delete("/plans/{plan_id}")
def delete_schedule_plan(
    plan_id: str, current_user: User = Depends(get_current_user)
):
    try:
        return plan_commands.delete_plan(plan_id, current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.get("/presets")
def list_schedule_presets(current_user: User = Depends(get_current_user)):
    """Bibliothèque de presets 2026 (modèles + plans éditables)."""
    try:
        return plan_commands.list_presets(current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/presets/apply")
def apply_schedule_preset(
    payload: ApplyPresetRequest, current_user: User = Depends(get_current_user)
):
    """Matérialise un preset en modèles + plans éditables pour l'entreprise active."""
    try:
        return plan_commands.apply_preset(payload.preset_key, current_user)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/generate")
def generate_planned_calendars(
    payload: GenerateCalendarRequest, current_user: User = Depends(get_current_user)
):
    """Génère (ou prévisualise en dry-run) les calendriers d'un plan."""
    try:
        return plan_commands.generate(payload, current_user)
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
    if progress_raw.get("batch_id"):
        progress = progress.model_copy(
            update={"batch_id": str(progress_raw.get("batch_id"))}
        )
    if progress_raw.get("files_total"):
        progress = progress.model_copy(
            update={
                "files_total": int(progress_raw.get("files_total") or 0),
                "files_done": int(progress_raw.get("files_done") or 0),
            }
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Enregistre en batch les jours proposés (merge prevu/réel par employé)."""
    from app.modules.schedules.application.persist_timesheet import (
        run_persist_with_bulk_commit,
        validate_persist_payload,
    )
    from app.modules.schedules.application.timesheet_import.commit_service import (
        begin_commit_batch,
        run_commit_batch,
    )
    from app.modules.schedules.application.timesheet_import.job_runner import (
        BackgroundTasksRunner,
    )

    company_id = str(current_user.active_company_id)
    try:
        validate_persist_payload(payload)
        if payload.batch_id:
            commit_req = TimesheetImportCommitRequest(
                allow_partial=payload.allow_partial,
                recalculate_payroll=payload.recalculate_payroll,
                employee_ids=[e.employee_id for e in payload.employees] or None,
            )
            if begin_commit_batch(
                payload.batch_id,
                company_id=company_id,
                request=commit_req,
            ):
                runner = BackgroundTasksRunner(background_tasks)
                runner.enqueue(
                    run_commit_batch,
                    payload.batch_id,
                    company_id=company_id,
                    request=commit_req,
                    user_id=str(current_user.id),
                )
            return PersistTimesheetResponse(
                year=payload.year,
                month=payload.month,
                employees_processed=len(payload.employees),
                total_days_written=0,
                results=[],
                errors=[],
            )
        return run_persist_with_bulk_commit(
            payload,
            company_id=company_id,
            user_id=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ScheduleAppError as e:
        _handle_schedule_error(e)


# ----- Import pointages staging (batch/items) -----


@router_rh.post(
    "/timesheet-import/detect-columns",
    response_model=None,
)
async def timesheet_import_detect_columns(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Preview colonnes CSV/XLSX sans persister."""
    from app.modules.schedules.application.timesheet_import.parse_service import (
        detect_columns,
    )
    from app.modules.schedules.schemas.timesheet_import import ColumnDetectionResponse

    _ = current_user
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Le fichier est vide.")
    try:
        result = detect_columns(content, file.filename or "import.csv")
        return ColumnDetectionResponse.model_validate(result)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router_rh.post("/timesheet-import/parse")
async def timesheet_import_parse(
    file: UploadFile = File(...),
    year: int = Form(...),
    month: int = Form(...),
    employees: str = Form("[]"),
    column_mapping: str = Form("{}"),
    profile_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Parse synchrone CSV/XLSX/PDF déterministe → batch previewed."""
    from app.modules.schedules.application.timesheet_import.parse_service import (
        parse_structured_file,
    )
    from app.modules.schedules.schemas.ai import RosterEmployee
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportParseResponse

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Le fichier est vide.")
    try:
        raw_roster = json.loads(employees or "[]")
        roster = [RosterEmployee(**item) for item in raw_roster]
        mapping = json.loads(column_mapping or "{}")
    except (json.JSONDecodeError, TypeError, ValueError):
        roster = []
        mapping = {}

    try:
        result = parse_structured_file(
            company_id=str(current_user.active_company_id),
            user_id=str(current_user.id),
            content=content,
            filename=file.filename or "import.csv",
            year=year,
            month=month,
            roster=roster,
            column_mapping=mapping or None,
            profile_name=profile_name,
        )
        return TimesheetImportParseResponse.model_validate(result)
    except ScheduleAppError as e:
        _handle_schedule_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Impossible de lire ce fichier Excel/CSV : {e}",
        ) from e


@router_rh.get("/timesheet-import/batches/{batch_id}")
async def timesheet_import_get_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application.timesheet_import.parse_service import (
        get_batch_response,
    )
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportBatchResponse

    try:
        data = get_batch_response(batch_id, company_id=str(current_user.active_company_id))
        return TimesheetImportBatchResponse.model_validate(data)
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/timesheet-import/batches/{batch_id}/commit")
async def timesheet_import_commit_batch(
    batch_id: str,
    background_tasks: BackgroundTasks,
    body: TimesheetImportCommitRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        begin_commit_batch,
        run_commit_batch,
    )
    from app.modules.schedules.application.timesheet_import.job_runner import (
        BackgroundTasksRunner,
    )
    from app.modules.schedules.schemas.timesheet_import import (
        TimesheetImportCommitRequest,
        TimesheetImportCommitStartResponse,
    )

    company_id = str(current_user.active_company_id)
    request = body or TimesheetImportCommitRequest()
    try:
        if not begin_commit_batch(batch_id, company_id=company_id, request=request):
            return TimesheetImportCommitStartResponse(batch_id=batch_id, status="committing")
        runner = BackgroundTasksRunner(background_tasks)
        runner.enqueue(
            run_commit_batch,
            batch_id,
            company_id=company_id,
            request=request,
            user_id=str(current_user.id),
        )
        return TimesheetImportCommitStartResponse(batch_id=batch_id, status="committing")
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/timesheet-import/extract-timesheet/start-batch")
async def timesheet_import_start_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    year: int = Form(...),
    month: int = Form(...),
    employees: str = Form("[]"),
    single_employee: bool = Form(False),
    document_scope: str = Form("auto"),
    current_user: User = Depends(get_current_user),
):
    """Lance l'extraction de plusieurs relevés en un job fusionné."""
    from app.modules.schedules.application.timesheet_import.job_runner import (
        BackgroundTasksRunner,
    )
    from app.modules.schedules.application.timesheet_import_service import (
        create_import_job,
        run_multi_timesheet_extraction_job,
    )
    from app.modules.schedules.schemas.timesheet_import import (
        TimesheetImportMultiStartResponse,
    )

    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni.")
    contents: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()
        if data:
            contents.append((f.filename or "document.pdf", data))

    request_json = {
        "year": year,
        "month": month,
        "employees": json.loads(employees or "[]"),
        "single_employee": single_employee,
        "document_scope": document_scope,
        "multi_file": True,
    }
    first_name, first_content = contents[0]
    try:
        job = create_import_job(
            company_id=str(current_user.active_company_id),
            user_id=str(current_user.id),
            filename=f"{len(contents)} fichiers",
            file_content=first_content,
            request_json=request_json,
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)

    job_id = str(job["id"])
    runner = BackgroundTasksRunner(background_tasks)
    runner.enqueue(run_multi_timesheet_extraction_job, job_id, contents)

    return TimesheetImportMultiStartResponse(
        job_id=job_id,
        batch_id=job_id,
        status="extracting",
        file_count=len(contents),
    )


@router_rh.get("/timesheet-import/profiles")
async def timesheet_import_list_profiles(
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application.timesheet_import.parse_service import (
        list_import_profiles,
    )
    from app.modules.schedules.schemas.timesheet_import import TimesheetImportProfile

    rows = list_import_profiles(str(current_user.active_company_id))
    return [TimesheetImportProfile.model_validate(r) for r in rows]


@router_rh.put("/timesheet-import/profiles")
async def timesheet_import_save_profile(
    payload: TimesheetImportProfileUpdate,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application.timesheet_import.parse_service import (
        save_import_profile,
    )
    from app.modules.schedules.schemas.timesheet_import import (
        TimesheetImportProfile,
    )

    row = save_import_profile(
        str(current_user.active_company_id),
        payload.model_dump(),
    )
    return TimesheetImportProfile.model_validate(row)


# ----- Comptabilisation pointages -----


@router_rh.get("/punch-accounting/settings")
async def punch_accounting_get_settings(
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac
    from app.modules.schedules.schemas.punch_accounting import (
        PunchAccountingSettingsResponse,
    )

    return PunchAccountingSettingsResponse.model_validate(
        pac.get_punch_accounting_settings(str(current_user.active_company_id))
    )


@router_rh.patch("/punch-accounting/settings")
async def punch_accounting_update_settings(
    payload: PunchAccountingSettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac
    from app.modules.schedules.schemas.punch_accounting import (
        PunchAccountingSettingsResponse,
    )
    try:
        return PunchAccountingSettingsResponse.model_validate(
            pac.update_punch_accounting_settings(
                str(current_user.active_company_id), payload
            )
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.post("/punch-accounting/settings/apply-preset/{preset}")
async def punch_accounting_apply_preset(
    preset: str,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac

    try:
        return pac.apply_punch_accounting_preset(
            str(current_user.active_company_id), preset
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.get("/punch-accounting/slots")
async def punch_accounting_list_slots(
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac

    return pac.list_punch_shift_slots(str(current_user.active_company_id))


@router_rh.post("/punch-accounting/slots")
async def punch_accounting_create_slot(
    payload: PunchShiftSlotCreate,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac
    return pac.create_punch_shift_slot(str(current_user.active_company_id), payload)


@router_rh.patch("/punch-accounting/slots/{slot_id}")
async def punch_accounting_update_slot(
    slot_id: str,
    payload: PunchShiftSlotUpdate,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac
    try:
        return pac.update_punch_shift_slot(
            str(current_user.active_company_id), slot_id, payload
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.delete("/punch-accounting/slots/{slot_id}")
async def punch_accounting_delete_slot(
    slot_id: str,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac

    try:
        pac.delete_punch_shift_slot(str(current_user.active_company_id), slot_id)
        return {"status": "ok"}
    except ScheduleAppError as e:
        _handle_schedule_error(e)


@router_rh.get("/punch-overtime-reviews")
async def punch_overtime_list_reviews(
    year: int,
    month: int,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac

    return pac.list_punch_overtime_reviews(
        str(current_user.active_company_id),
        year=year,
        month=month,
        status=status,
    )


@router_rh.patch("/punch-overtime-reviews/{review_id}")
async def punch_overtime_update_review(
    review_id: str,
    payload: PunchOvertimeReviewUpdate,
    current_user: User = Depends(get_current_user),
):
    from app.modules.schedules.application import punch_accounting_commands as pac
    try:
        return pac.update_punch_overtime_review(
            str(current_user.active_company_id),
            review_id,
            payload,
            reviewed_by=str(current_user.id),
        )
    except ScheduleAppError as e:
        _handle_schedule_error(e)


__all__ = ["router", "router_me", "router_rh"]
