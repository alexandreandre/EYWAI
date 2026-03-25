"""
Routes /api/uploads/* : logos entreprise/groupe, fichiers BDES (storage).

Utilise le client Supabase admin pour l’accès storage (upsert, URLs signées).
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status

from app.core.database import get_supabase_admin_client
from app.core.security import get_current_user
from app.modules.company_groups.application.service import (
    get_group_company_ids_for_permission_check,
)
from app.modules.cse.application.queries import check_module_active
from app.modules.uploads.schemas import BdesUploadResponse, UploadLogoResponse
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

BUCKET_LOGOS = "logos"
BUCKET_BDES = "cse-documents"

_ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def _admin():
    return get_supabase_admin_client()


def _signed_url(sb, bucket: str, path: str) -> str:
    signed = sb.storage.from_(bucket).create_signed_url(
        path,
        31536000,
        options={"download": False},
    )
    url = signed.get("signedURL") if isinstance(signed, dict) else None
    if not url:
        raise HTTPException(
            status_code=500,
            detail="Impossible de générer l’URL du fichier",
        )
    return url


def _ensure_company_logo(user: User, company_id: str) -> None:
    if not user.has_access_to_company(company_id):
        raise HTTPException(status_code=403, detail="Accès refusé à cette entreprise.")
    if not user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Droits insuffisants pour modifier le logo.",
        )


def _ensure_group_logo(user: User, group_id: str) -> None:
    if user.is_super_admin:
        return
    company_ids = get_group_company_ids_for_permission_check(group_id)
    if not company_ids:
        raise HTTPException(status_code=404, detail="Groupe introuvable.")
    for cid in company_ids:
        if not user.is_admin_in_company(cid):
            raise HTTPException(
                status_code=403,
                detail="Vous devez être admin de toutes les entreprises du groupe.",
            )


def _require_rh_bdes(user: User) -> str:
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


def _safe_upload_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return (cleaned[:180] or "document").lower()


@router.post("/logo", response_model=UploadLogoResponse)
async def upload_logo(
    file: UploadFile = File(...),
    entity_type: Literal["company", "group"] = Form(...),
    entity_id: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    """Upload un logo (PNG, JPG, WebP, SVG, max 2 Mo)."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_LOGO_EXT:
        raise HTTPException(
            status_code=400,
            detail="Format non supporté (PNG, JPG, WebP, SVG).",
        )
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 2 Mo).")

    if entity_type == "company":
        _ensure_company_logo(current_user, entity_id)
        exist = _admin().table("companies").select("id").eq("id", entity_id).execute()
        if not exist.data:
            raise HTTPException(status_code=404, detail="Entreprise introuvable.")
    else:
        _ensure_group_logo(current_user, entity_id)
        exist = (
            _admin().table("company_groups").select("id").eq("id", entity_id).execute()
        )
        if not exist.data:
            raise HTTPException(status_code=404, detail="Groupe introuvable.")

    sb = _admin()
    storage_path = f"{entity_type}/{entity_id}/{uuid.uuid4().hex}{ext}"
    ctype = file.content_type or "application/octet-stream"
    sb.storage.from_(BUCKET_LOGOS).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": ctype, "x-upsert": "true"},
    )
    logo_url = _signed_url(sb, BUCKET_LOGOS, storage_path)

    if entity_type == "company":
        sb.table("companies").update({"logo_url": logo_url}).eq("id", entity_id).execute()
    else:
        sb.table("company_groups").update({"logo_url": logo_url}).eq("id", entity_id).execute()

    return UploadLogoResponse(logo_url=logo_url)


@router.delete("/logo/{entity_type}/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_logo(
    entity_type: Literal["company", "group"],
    entity_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime le logo (storage + URL en base)."""
    if entity_type == "company":
        _ensure_company_logo(current_user, entity_id)
        table = "companies"
    else:
        _ensure_group_logo(current_user, entity_id)
        table = "company_groups"

    sb = _admin()
    exists = sb.table(table).select("id").eq("id", entity_id).limit(1).execute()
    if not exists.data:
        raise HTTPException(status_code=404, detail="Entité introuvable.")

    prefix = f"{entity_type}/{entity_id}"
    try:
        listed = sb.storage.from_(BUCKET_LOGOS).list(prefix)
    except Exception:
        listed = []
    names = [item.get("name") for item in (listed or []) if item.get("name")]
    paths = [f"{prefix}/{n}" for n in names]
    if paths:
        try:
            sb.storage.from_(BUCKET_LOGOS).remove(paths)
        except Exception:
            pass

    sb.table(table).update({"logo_url": None}).eq("id", entity_id).execute()


@router.patch("/logo-scale/{entity_type}/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def patch_logo_scale(
    entity_type: Literal["company", "group"],
    entity_id: str,
    scale: float = Query(..., ge=0.5, le=2.0),
    current_user: User = Depends(get_current_user),
):
    """Met à jour le facteur d’affichage du logo (0,5 à 2)."""

    if entity_type == "company":
        _ensure_company_logo(current_user, entity_id)
        table = "companies"
    else:
        _ensure_group_logo(current_user, entity_id)
        table = "company_groups"

    sb = _admin()
    exists = sb.table(table).select("id").eq("id", entity_id).limit(1).execute()
    if not exists.data:
        raise HTTPException(status_code=404, detail="Entité introuvable.")
    sb.table(table).update({"logo_scale": scale}).eq("id", entity_id).execute()


@router.post("/bdes", response_model=BdesUploadResponse)
async def upload_bdes_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Enregistre un fichier BDES dans le stockage ; retourne le chemin pour
    enchaînement avec POST /api/cse/bdes-documents (flux modal).
    """
    company_id = _require_rh_bdes(current_user)
    check_module_active(company_id)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    safe = _safe_upload_filename(file.filename or "")
    path = f"bdes/{company_id}/{uuid.uuid4().hex}_{safe}"
    sb = _admin()
    sb.storage.from_(BUCKET_BDES).upload(
        path=path,
        file=content,
        file_options={
            "content-type": file.content_type or "application/octet-stream",
            "x-upsert": "true",
        },
    )
    return BdesUploadResponse(path=path)
