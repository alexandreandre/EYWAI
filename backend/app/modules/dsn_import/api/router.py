"""Routes API import DSN (super-admin)."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.modules.dsn_import.api.dependencies import verify_super_admin
from app.modules.dsn_import.application import service
from app.modules.dsn_import.schemas.requests import (
    ActivateImportedEmployeeBody,
    DsnImportCommitBody,
)
from app.modules.dsn_import.schemas.responses import (
    ActivateImportedEmployeeResponse,
    DsnImportBatchDetailResponse,
    DsnImportBatchListResponse,
    DsnImportBatchSummary,
    DsnImportCommitResponse,
    DsnImportParseResponse,
    ImportedEmployeeSummary,
)

router = APIRouter(prefix="/api/dsn-import", tags=["Import DSN"])


@router.post("/parse", response_model=DsnImportParseResponse)
async def parse_dsn_files(
    files: List[UploadFile] = File(...),
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> DsnImportParseResponse:
    """Upload et analyse de un ou plusieurs fichiers DSN."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni.")

    payloads: List[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Fichier vide : {f.filename}")
        payloads.append((f.filename or "dsn.txt", content))

    try:
        result = service.parse_and_stage(payloads, uploaded_by=str(super_admin.get("user_id")))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return DsnImportParseResponse(**result)


@router.get("/batches", response_model=DsnImportBatchListResponse)
async def list_import_batches(
    limit: int = 50,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> DsnImportBatchListResponse:
    rows = service.list_batches(limit=limit)
    batches = [
        DsnImportBatchSummary(
            id=str(r["id"]),
            uploaded_by=str(r.get("uploaded_by", "")),
            file_names=r.get("file_names") or [],
            siren=r.get("siren"),
            period_min=r.get("period_min"),
            period_max=r.get("period_max"),
            status=r.get("status", "parsed"),
            summary=r.get("summary") or {},
            created_at=r.get("created_at"),
            updated_at=r.get("updated_at"),
        )
        for r in rows
    ]
    return DsnImportBatchListResponse(batches=batches)


@router.get("/batches/{batch_id}", response_model=DsnImportBatchDetailResponse)
async def get_import_batch(
    batch_id: str,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> DsnImportBatchDetailResponse:
    detail = service.get_batch_detail(batch_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Batch introuvable.")
    b = detail["batch"]
    return DsnImportBatchDetailResponse(
        batch=DsnImportBatchSummary(
            id=str(b["id"]),
            uploaded_by=str(b.get("uploaded_by", "")),
            file_names=b.get("file_names") or [],
            siren=b.get("siren"),
            period_min=b.get("period_min"),
            period_max=b.get("period_max"),
            status=b.get("status", "parsed"),
            summary=b.get("summary") or {},
            created_at=b.get("created_at"),
            updated_at=b.get("updated_at"),
        ),
        items=detail.get("items") or [],
        preview=detail.get("preview") or {},
        summary=detail.get("summary") or {},
    )


@router.post("/batches/{batch_id}/commit", response_model=DsnImportCommitResponse)
async def commit_import_batch(
    batch_id: str,
    body: DsnImportCommitBody,
    _super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> DsnImportCommitResponse:
    """Valide et exécute l'import DSN."""
    try:
        report = service.execute_commit(batch_id, overrides=body.overrides)
    except LookupError:
        raise HTTPException(status_code=404, detail="Batch introuvable.") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return DsnImportCommitResponse(
        stats=report.get("stats") or {},
        errors=report.get("errors") or [],
        group_id=report.get("group_id"),
        companies=report.get("companies") or {},
        imported_employees=[
            ImportedEmployeeSummary(**row)
            for row in (report.get("imported_employees") or [])
        ],
    )


@router.post("/employees/activate", response_model=ActivateImportedEmployeeResponse)
async def activate_imported_employee(
    body: ActivateImportedEmployeeBody,
    super_admin: Dict[str, Any] = Depends(verify_super_admin),
) -> ActivateImportedEmployeeResponse:
    """Crée le compte Auth d'un salarié importé DSN (activation différée)."""
    try:
        result = service.activate_imported_employee(
            employee_id=body.employee_id,
            company_id=body.company_id,
            email=body.email,
            granted_by_user_id=str(super_admin.get("user_id")),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ActivateImportedEmployeeResponse(
        employee_id=str(result["employee_id"]),
        user_id=str(result["user_id"]),
        email=str(result["email"]),
        generated_password=str(result["generated_password"]),
    )
