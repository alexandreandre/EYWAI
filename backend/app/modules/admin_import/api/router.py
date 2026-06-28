"""Routes API import admin (super-admin)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from app.modules.admin_import.api.dependencies import (
    super_admin_auth_user_id,
    verify_super_admin,
)
from app.modules.admin_import.application import cp_import, payroll_export_import, rib_import, seniority_import
from app.modules.admin_import.application.ccn_preset_apply import apply_ccn_setup_presets
from app.modules.admin_import.application.company_setup_status import get_company_setup_status
from app.modules.admin_import.application.planning_import import (
    begin_planning_import_commit,
    parse_planning_import,
    run_planning_import_commit,
)
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.admin_import.application.planning_import_mappings import (
    apply_planning_manual_mappings,
)
from app.modules.admin_import.schemas.requests import (
    CpImportCommitBody,
    PayrollExportCommitBody,
    PlanningImportApplyMappingsBody,
    RibImportCommitBody,
    SeniorityImportCommitBody,
)
from app.modules.admin_import.schemas.responses import (
    CcnPresetApplyResponse,
    CompanySetupStatusResponse,
    CpImportCommitResponse,
    CpImportParseResponse,
    PayrollExportCommitResponse,
    PayrollExportParseResponse,
    PlanningImportApplyMappingsResponse,
    PlanningImportBatchStatusResponse,
    PlanningImportCommitResponse,
    PlanningImportParseResponse,
    RibImportCommitResponse,
    RibImportParseResponse,
    SeniorityImportCommitResponse,
    SeniorityImportParseResponse,
)

router = APIRouter(prefix="/api/admin-import", tags=["Import"])


@router.get("/company-setup-status", response_model=CompanySetupStatusResponse)
def company_setup_status(
    company_id: str = Query(..., description="Entreprise cible"),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> CompanySetupStatusResponse:
    try:
        result = get_company_setup_status(company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CompanySetupStatusResponse(**result)


@router.post("/ccn-preset/apply", response_model=CcnPresetApplyResponse)
def apply_ccn_preset(
    company_id: str = Query(..., description="Entreprise cible"),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> CcnPresetApplyResponse:
    try:
        result = apply_ccn_setup_presets(company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CcnPresetApplyResponse(**result)


@router.post("/planning/parse", response_model=PlanningImportParseResponse)
async def parse_planning_import_route(
    file: UploadFile = File(...),
    company_id: str = Query(...),
    year: int = Query(...),
    period_mode: str = Query("month", pattern="^(auto|month|year|range)$"),
    month: int | None = Query(None, ge=1, le=12),
    start_year: int | None = Query(None),
    start_month: int | None = Query(None, ge=1, le=12),
    end_year: int | None = Query(None),
    end_month: int | None = Query(None, ge=1, le=12),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PlanningImportParseResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    if period_mode == "month" and month is None:
        raise HTTPException(status_code=400, detail="Le mois est requis pour un import mensuel.")
    if period_mode == "range" and (
        start_year is None or start_month is None or end_year is None or end_month is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Précisez le début et la fin de la plage (année et mois).",
        )
    try:
        result = parse_planning_import(
            content,
            file.filename or "import.csv",
            company_id,
            year,
            month,
            period_mode=period_mode,  # type: ignore[arg-type]
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            user_id=super_admin_auth_user_id(_super_admin),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScheduleAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    preview = result.get("preview")
    if hasattr(preview, "model_dump"):
        preview = preview.model_dump(mode="json")
    effective_month = month if month is not None else (start_month or 1)
    return PlanningImportParseResponse(
        company_id=company_id,
        company_name=result.get("company_name") or "Entreprise",
        year=year,
        month=effective_month,
        period_mode=period_mode,
        batch_id=str(result.get("batch_id") or ""),
        status=str(result.get("status") or "previewed"),
        preview=preview,
        summary=result.get("summary"),
        roster=result.get("roster") or [],
        parser_key=result.get("parser_key"),
        file_hash=result.get("file_hash"),
    )


@router.post("/planning/commit", response_model=PlanningImportCommitResponse)
async def commit_planning_import_route(
    background_tasks: BackgroundTasks,
    batch_id: str = Query(...),
    company_id: str = Query(...),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PlanningImportCommitResponse:
    from app.modules.schedules.application.timesheet_import.job_runner import (
        BackgroundTasksRunner,
    )

    try:
        result = begin_planning_import_commit(
            batch_id,
            company_id,
            user_id=super_admin_auth_user_id(_super_admin),
        )
        if result.pop("launch_background", False):
            runner = BackgroundTasksRunner(background_tasks)
            runner.enqueue(
                run_planning_import_commit,
                batch_id,
                company_id,
                user_id=super_admin_auth_user_id(_super_admin),
            )
    except ScheduleAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlanningImportCommitResponse(**result)


@router.get("/planning/batches/{batch_id}", response_model=PlanningImportBatchStatusResponse)
def get_planning_import_batch_route(
    batch_id: str,
    company_id: str = Query(...),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PlanningImportBatchStatusResponse:
    from app.modules.schedules.application.timesheet_import.parse_service import (
        get_batch_response,
    )

    try:
        data = get_batch_response(batch_id, company_id=company_id)
    except ScheduleAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    summary = data.get("summary") or {}
    commit_progress = summary.get("commit_progress")
    return PlanningImportBatchStatusResponse(
        batch_id=str(data.get("batch_id") or batch_id),
        status=str(data.get("status") or "unknown"),
        summary=summary,
        commit_progress=commit_progress,
        employees_processed=summary.get("employees_processed"),
        total_days_written=summary.get("committed_days"),
        errors=list(summary.get("commit_errors") or []),
        error_message=data.get("error_message"),
    )


@router.post("/planning/apply-mappings", response_model=PlanningImportApplyMappingsResponse)
def apply_planning_import_mappings_route(
    body: PlanningImportApplyMappingsBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PlanningImportApplyMappingsResponse:
    try:
        result = apply_planning_manual_mappings(
            body.batch_id,
            body.company_id,
            [m.model_dump() for m in body.mappings],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScheduleAppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return PlanningImportApplyMappingsResponse(**result)


@router.post("/rib/parse", response_model=RibImportParseResponse)
async def parse_rib_import(
    file: UploadFile = File(...),
    company_id: str = Query(..., description="Entreprise cible"),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> RibImportParseResponse:
    """Analyse un fichier Excel/CSV avec colonne RIB et rapproche les employés."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    try:
        result = rib_import.parse_rib_import_file(
            content,
            file.filename or "import.xlsx",
            company_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RibImportParseResponse(**result)


@router.post("/rib/commit", response_model=RibImportCommitResponse)
def commit_rib_import(
    body: RibImportCommitBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> RibImportCommitResponse:
    """Enregistre les RIB validés pour les employés sélectionnés."""
    try:
        result = rib_import.commit_rib_import(body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RibImportCommitResponse(**result)


@router.post("/seniority/parse", response_model=SeniorityImportParseResponse)
async def parse_seniority_import(
    file: UploadFile = File(...),
    company_id: str = Query(..., description="Entreprise cible"),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> SeniorityImportParseResponse:
    """Analyse un fichier Excel/CSV de dates d'ancienneté (reprise / prime)."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    try:
        result = seniority_import.parse_seniority_import_file(
            content,
            file.filename or "anciennete.xlsx",
            company_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SeniorityImportParseResponse(**result)


@router.post("/seniority/commit", response_model=SeniorityImportCommitResponse)
def commit_seniority_import(
    body: SeniorityImportCommitBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> SeniorityImportCommitResponse:
    """Enregistre les dates d'ancienneté validées."""
    try:
        result = seniority_import.commit_seniority_import(body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SeniorityImportCommitResponse(**result)


@router.post("/cp/parse", response_model=CpImportParseResponse)
async def parse_cp_import(
    files: List[UploadFile] = File(...),
    company_id: str | None = Query(
        None,
        description="Filiale ciblée (parcours guidé) — fallback si SIRET bulletin absent.",
    ),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> CpImportParseResponse:
    """Analyse un ou plusieurs bulletins PDF et extrait les soldes CP."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni.")
    payloads: List[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        payloads.append((upload.filename or "bulletin.pdf", content))
    try:
        result = cp_import.parse_cp_import_files(
            payloads,
            target_company_id=company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CpImportParseResponse(**result)


@router.post("/cp/commit", response_model=CpImportCommitResponse)
def commit_cp_import(
    body: CpImportCommitBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> CpImportCommitResponse:
    """Enregistre les soldes CP validés."""
    result = cp_import.commit_cp_import(body)
    return CpImportCommitResponse(**result)


@router.post("/payroll-export/parse", response_model=PayrollExportParseResponse)
async def parse_payroll_export_import(
    file: UploadFile = File(...),
    company_id: str = Query(..., description="Entreprise cible"),
    map_mod_moi_teams: Optional[bool] = Query(
        None,
        description="Mapper la colonne Service vers les équipes MOD/MOI (None = auto)",
    ),
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PayrollExportParseResponse:
    """Analyse un export paie Quadra/Cegid et rapproche les salariés existants."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    try:
        result = payroll_export_import.parse_payroll_export_file(
            content,
            file.filename or "export.xlsx",
            company_id,
            map_mod_moi_teams=map_mod_moi_teams,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return PayrollExportParseResponse(**result)


@router.post("/payroll-export/commit", response_model=PayrollExportCommitResponse)
def commit_payroll_export_import(
    body: PayrollExportCommitBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> PayrollExportCommitResponse:
    """Enregistre les données enrichies pour les salariés sélectionnés."""
    try:
        result = payroll_export_import.commit_payroll_export(body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PayrollExportCommitResponse(**result)
