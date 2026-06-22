"""Routes API import admin (super-admin)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.modules.admin_import.api.dependencies import verify_super_admin
from app.modules.admin_import.application import rib_import
from app.modules.admin_import.schemas.requests import RibImportCommitBody
from app.modules.admin_import.schemas.responses import (
    RibImportCommitResponse,
    RibImportParseResponse,
)

router = APIRouter(prefix="/api/admin-import", tags=["Import"])


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
