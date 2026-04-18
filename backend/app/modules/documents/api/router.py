"""Routes /api/documents."""

from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.documents.application import commands, queries
from app.modules.documents.schemas.requests import (
    GenerateDocumentRequest,
    UpdateDocumentStatusRequest,
)
from app.modules.documents.schemas.responses import DownloadUrlResponse, GeneratedDocument
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/documents", tags=["Documents"])


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


def _require_rh(user: User, company_id: str) -> None:
    if not user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )
    if not user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH")


def _require_company_access(user: User, company_id: str) -> None:
    if not user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


def _row_to_generated(row: dict) -> GeneratedDocument:
    gc = row.get("generation_context")
    if not isinstance(gc, dict):
        gc = {}
    return GeneratedDocument(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        employee_id=str(row["employee_id"]) if row.get("employee_id") else None,
        document_type=str(row["document_type"]),
        category=str(row["category"]),
        template_id=str(row["template_id"]) if row.get("template_id") else None,
        template_version_id=str(row["template_version_id"])
        if row.get("template_version_id")
        else None,
        is_eywai_template=bool(row.get("is_eywai_template")),
        file_url=str(row["file_url"]) if row.get("file_url") else None,
        file_name=str(row["file_name"]) if row.get("file_name") else None,
        status=str(row["status"]),
        generation_context=gc,
        generated_by=str(row["generated_by"]) if row.get("generated_by") else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        employee_name=row.get("employee_name"),
        template_name=row.get("template_name"),
    )


@router.get("/", response_model=List[GeneratedDocument])
def list_documents_route(
    employee_id: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = Query(None, description="ISO date (inclus)"),
    date_to: Optional[str] = Query(None, description="ISO date (inclus)"),
    current_user: User = Depends(get_current_user),
) -> List[GeneratedDocument]:
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    try:
        if current_user.has_rh_access_in_company(cid):
            rows = queries.get_documents(
                cid,
                employee_id=employee_id,
                document_type=document_type,
                status=status,
                date_from=date_from,
                date_to=date_to,
            )
        else:
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp:
                raise HTTPException(
                    status_code=403,
                    detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
                )
            if employee_id and employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès non autorisé.")
            rows = queries.get_documents(
                cid,
                employee_id=my_emp,
                document_type=document_type,
                status=status,
                date_from=date_from,
                date_to=date_to,
            )
        return [_row_to_generated(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.post("/generate", response_model=GeneratedDocument, status_code=201)
def generate_document_route(
    body: GenerateDocumentRequest,
    current_user: User = Depends(get_current_user),
) -> GeneratedDocument:
    cid = _company_id(current_user)
    _require_rh(current_user, cid)
    try:
        row = commands.generate_document(cid, str(current_user.id), body)
        return _row_to_generated(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get("/{document_id}/download", response_model=DownloadUrlResponse)
def download_document_route(
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> DownloadUrlResponse:
    """Retourne une URL signée (téléchargement côté client)."""
    cid = _company_id(current_user)
    _require_company_access(current_user, cid)
    try:
        if current_user.has_rh_access_in_company(cid):
            url = queries.get_download_url(document_id, cid)
            return DownloadUrlResponse(signed_url=url)
        my_emp = _employee_scope_id(current_user, cid)
        if not my_emp:
            raise HTTPException(
                status_code=403,
                detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
            )
        row = queries.get_document(document_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Document introuvable")
        if str(row.get("employee_id") or "") != str(my_emp):
            raise HTTPException(status_code=403, detail="Accès non autorisé.")
        url = queries.get_download_url(document_id, cid)
        return DownloadUrlResponse(signed_url=url)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.put("/{document_id}/status", response_model=GeneratedDocument)
def update_status_route(
    document_id: str,
    body: UpdateDocumentStatusRequest,
    current_user: User = Depends(get_current_user),
) -> GeneratedDocument:
    cid = _company_id(current_user)
    _require_rh(current_user, cid)
    try:
        row = commands.update_document_status(document_id, cid, body)
        return _row_to_generated(row)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.delete("/{document_id}", status_code=204)
def delete_document_route(
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    cid = _company_id(current_user)
    _require_rh(current_user, cid)
    try:
        commands.delete_document(document_id, cid)
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)


@router.get("/{document_id}", response_model=GeneratedDocument)
def get_document_route(
    document_id: str,
    current_user: User = Depends(get_current_user),
) -> GeneratedDocument:
    cid = _company_id(current_user)
    _require_rh(current_user, cid)
    try:
        row = queries.get_document(document_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Document introuvable")
        return _row_to_generated(row)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        _handle_application_errors(e)
