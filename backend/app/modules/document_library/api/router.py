"""Routes HTTP /api/document-library."""

from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.security import get_current_user
from app.modules.document_library.application import commands, queries
from app.modules.document_library.schemas.requests import DocumentTemplateCreate, DocumentTemplateUpdate
from app.modules.document_library.schemas.responses import (
    DocumentTemplate,
    DocumentTemplateVersion,
    DocumentTemplateVersionUpload,
    DocumentVariableItem,
    DocumentVariablesResponse,
    SignedVersionDownload,
    ValidateTemplateFileResponse,
)
from app.modules.users.schemas.responses import User
from app.services.document_variables import list_document_variables

router = APIRouter(prefix="/api/document-library", tags=["DocumentLibrary"])


def _handle_application_errors(e: Exception) -> None:
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    raise


def _company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(cid)


def _require_company_access(user: User, company_id: str) -> None:
    if not user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )


def _can_read_library(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    return user.has_rh_access_in_company(company_id)


def _can_write_library(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    role = user.get_role_in_company(company_id)
    return role in ("admin", "rh", "collaborateur_rh")


def _is_primary_hr_or_admin(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    if user.is_admin_in_company(company_id):
        return True
    for access in user.accessible_companies:
        if access.company_id == company_id and access.role == "rh" and access.is_primary:
            return True
    return False


def _parse_dt(v: object) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    raise ValueError("Date invalide")


def _version_from_row(row: dict) -> DocumentTemplateVersion:
    return DocumentTemplateVersion(
        id=str(row["id"]),
        template_id=str(row["template_id"]),
        version=int(row.get("version") or 0),
        file_url=str(row.get("file_url") or ""),
        file_name=str(row.get("file_name") or ""),
        file_format=str(row.get("file_format") or ""),
        file_size=row.get("file_size"),
        uploaded_by=str(row["uploaded_by"]) if row.get("uploaded_by") else None,
        created_at=_parse_dt(row["created_at"]),
    )


def _template_from_row(row: dict) -> DocumentTemplate:
    cv = row.get("current_version")
    return DocumentTemplate(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        document_type=str(row["document_type"]),
        name=str(row["name"]),
        is_default=bool(row.get("is_default")),
        status=str(row["status"]),
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
        current_version=_version_from_row(cv) if cv else None,
        versions_count=int(row.get("versions_count") or 0),
    )


def _version_upload_from_row(row: dict) -> DocumentTemplateVersionUpload:
    base = _version_from_row(row)
    return DocumentTemplateVersionUpload(
        **base.model_dump(),
        unknown_variables=list(row.get("unknown_variables") or []),
    )


@router.get("/variables", response_model=DocumentVariablesResponse)
def list_variables_route(
    current_user: User = Depends(get_current_user),
) -> DocumentVariablesResponse:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    items = [
        DocumentVariableItem(
            key=v["key"],
            label=v["label"],
            category=v["category"],
            example=v["example"],
        )
        for v in list_document_variables()
    ]
    return DocumentVariablesResponse(variables=items)


@router.post("/validate-file", response_model=ValidateTemplateFileResponse)
async def validate_file_route(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> ValidateTemplateFileResponse:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    raw = await file.read()
    fname = file.filename or "document"
    try:
        preview = commands.validate_template_bytes(raw, fname)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ValidateTemplateFileResponse(
        unknown_variables=list(preview.get("unknown_variables") or []),
        preview_available=bool(preview.get("preview_available")),
    )


_EXAMPLE_FICHE_POSTE = (
    Path(__file__).resolve().parents[3]
    / "static"
    / "document_templates"
    / "fiche_poste_exemple.docx"
)


@router.get("/examples/fiche_poste")
def download_fiche_poste_example_route(
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    if not _EXAMPLE_FICHE_POSTE.is_file():
        raise HTTPException(status_code=404, detail="Modèle exemple indisponible.")
    return FileResponse(
        path=_EXAMPLE_FICHE_POSTE,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        filename="fiche_poste_exemple.docx",
    )


@router.get("/", response_model=List[DocumentTemplate])
def list_templates_route(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> List[DocumentTemplate]:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    try:
        rows = queries.get_templates(cid, status=status)
        return [_template_from_row(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get("/missing-types", response_model=List[str])
def missing_types_route(current_user: User = Depends(get_current_user)) -> List[str]:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    try:
        return queries.get_missing_types(cid)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get("/{template_id}", response_model=DocumentTemplate)
def get_template_route(
    template_id: str,
    current_user: User = Depends(get_current_user),
) -> DocumentTemplate:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    try:
        row = queries.get_template(template_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Modèle introuvable")
        return _template_from_row(row)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.post("/", response_model=DocumentTemplate, status_code=201)
def create_template_route(
    body: DocumentTemplateCreate,
    current_user: User = Depends(get_current_user),
) -> DocumentTemplate:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_write_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Création réservée aux profils RH")
    try:
        row = commands.create_template(cid, body, str(current_user.id))
        return _template_from_row(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.put("/{template_id}", response_model=DocumentTemplate)
def update_template_route(
    template_id: str,
    body: DocumentTemplateUpdate,
    current_user: User = Depends(get_current_user),
) -> DocumentTemplate:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_write_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux profils RH")
    if body.is_default is True and not _is_primary_hr_or_admin(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Seul le RH principal ou un administrateur peut définir le modèle par défaut.",
        )
    try:
        row = commands.update_template(template_id, cid, body)
        return _template_from_row(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.post("/{template_id}/archive", response_model=DocumentTemplate)
def archive_template_route(
    template_id: str,
    current_user: User = Depends(get_current_user),
) -> DocumentTemplate:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _is_primary_hr_or_admin(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Archivage réservé au RH principal ou à un administrateur.",
        )
    try:
        row = commands.archive_template(template_id, cid)
        return _template_from_row(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get("/{template_id}/versions", response_model=List[DocumentTemplateVersion])
def list_versions_route(
    template_id: str,
    current_user: User = Depends(get_current_user),
) -> List[DocumentTemplateVersion]:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    try:
        rows = queries.get_versions(template_id, cid)
        return [_version_from_row(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.post("/{template_id}/upload", response_model=DocumentTemplateVersionUpload)
async def upload_template_route(
    template_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> DocumentTemplateVersionUpload:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_write_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Envoi de fichier réservé aux profils RH")
    try:
        raw = await file.read()
        fname = file.filename or "document"
        row = commands.upload_template_file(
            cid, template_id, raw, fname, str(current_user.id)
        )
        return _version_upload_from_row(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get(
    "/{template_id}/versions/{version_id}/download-url",
    response_model=SignedVersionDownload,
)
def version_download_url_route(
    template_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
) -> SignedVersionDownload:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _can_read_library(current_user, cid):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")
    try:
        url = queries.get_version_download_url(template_id, cid, version_id)
        return SignedVersionDownload(signed_url=url)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.post(
    "/{template_id}/versions/{version_id}/restore",
    response_model=DocumentTemplateVersion,
)
def restore_version_route(
    template_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
) -> DocumentTemplateVersion:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    if not _is_primary_hr_or_admin(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Restauration réservée au RH principal ou à un administrateur.",
        )
    try:
        row = commands.restore_version(
            template_id, cid, version_id, str(current_user.id)
        )
        return _version_from_row(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)
