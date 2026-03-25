"""
Routes /api/uploads/* : délégation stricte aux commandes applicatives.

Aucun accès persistance ici (garde d’architecture test_router_db_guard).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.core.security import get_current_user
from app.modules.cse.application.queries import check_module_active
from app.modules.uploads.application import commands as upload_commands
from app.modules.uploads.schemas import (
    BdesUploadResponse,
    DeleteLogoResponse,
    LogoScaleResponse,
    UploadLogoResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])


def _require_rh_bdes_company_id(user: User) -> str:
    if user.is_super_admin:
        if not user.active_company_id:
            raise HTTPException(
                status_code=400,
                detail="Aucune entreprise active sélectionnée.",
            )
        return str(user.active_company_id)
    cid = user.active_company_id
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="Aucune entreprise active sélectionnée.",
        )
    if not user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    return str(cid)


@router.post("/logo", response_model=UploadLogoResponse)
async def upload_logo(
    file: UploadFile = File(...),
    entity_type: Literal["company", "group"] = Form(...),
    entity_id: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """Upload un logo (PNG, JPG, WebP, SVG, max 2 Mo)."""
    content = await file.read()
    result = await upload_commands.upload_logo(
        file_content=content,
        content_type=file.content_type or "",
        filename=file.filename or "logo.png",
        entity_type=entity_type,
        entity_id=entity_id,
        current_user=current_user,
    )
    return UploadLogoResponse(logo_url=result.logo_url, message=result.message)


@router.delete("/logo/{entity_type}/{entity_id}", response_model=DeleteLogoResponse)
def delete_logo_route(
    entity_type: Literal["company", "group"],
    entity_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime le logo (storage + URL en base)."""
    result = upload_commands.delete_logo(
        entity_type=entity_type,
        entity_id=entity_id,
        current_user=current_user,
    )
    return DeleteLogoResponse(success=True, message=result.message)


@router.patch(
    "/logo-scale/{entity_type}/{entity_id}",
    response_model=LogoScaleResponse,
)
def patch_logo_scale_route(
    entity_type: Literal["company", "group"],
    entity_id: str,
    scale: float = Query(..., ge=0.5, le=2.0),
    current_user: User = Depends(get_current_user),
):
    """Met à jour Zoom du logo (0,5 à 2)."""
    result = upload_commands.update_logo_scale(
        entity_type=entity_type,
        entity_id=entity_id,
        scale=scale,
        current_user=current_user,
    )
    return LogoScaleResponse(
        success=True,
        logo_scale=result.logo_scale,
        message=result.message,
    )


@router.post("/bdes", response_model=BdesUploadResponse)
async def upload_bdes_route(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Dépose un fichier BDES dans le storage ; retourne le chemin pour le flux CSE."""
    company_id = _require_rh_bdes_company_id(current_user)
    check_module_active(company_id)

    content = await file.read()
    path = upload_commands.upload_bdes_storage_file(
        file_content=content,
        content_type=file.content_type,
        filename=file.filename or "document",
        company_id=company_id,
    )
    return BdesUploadResponse(path=path)
