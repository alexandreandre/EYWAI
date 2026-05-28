"""Routes REST certifications / habilitations."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user
from app.modules.certifications.application import commands, queries
from app.modules.certifications.schemas.requests import (
    CertificationRefCreate,
    CertificationRefUpdate,
    EmployeeCertificationCreate,
    EmployeeCertificationUpdate,
)
from app.modules.certifications.schemas.responses import (
    CertificationRef,
    DashboardCounts,
    EmployeeCertification,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/certifications", tags=["Certifications"])

MAX_CERT_UPLOAD = 5 * 1024 * 1024
ALLOWED_UPLOAD_CT = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
)


def _handle_application_errors(e: Exception) -> None:
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erreur inattendue: {str(e)}",
    )


def _company_id(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(
            status_code=400, detail="Aucune entreprise active sélectionnée."
        )
    return user.active_company_id


def _is_rh(user: User) -> bool:
    if is_platform_admin(user):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


# --- Ordre : routes statiques avant /{id} ---


@router.get("/dashboard-counts", response_model=DashboardCounts)
def route_dashboard_counts(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_dashboard_counts(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/refs", response_model=List[CertificationRef])
def route_list_refs(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_certification_refs(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/refs/{ref_id}", response_model=CertificationRef)
def route_get_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        out = queries.get_certification_ref(ref_id, _company_id(current_user))
        if out is None:
            raise HTTPException(status_code=404, detail="Référentiel non trouvé.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs", response_model=CertificationRef, status_code=201)
def route_create_ref(
    data: CertificationRefCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_certification_ref(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/refs/{ref_id}", response_model=CertificationRef)
def route_update_ref(
    ref_id: str,
    data: CertificationRefUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_certification_ref(
            ref_id, _company_id(current_user), data
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs/{ref_id}/archive", status_code=204)
def route_archive_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_certification_ref(ref_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("", response_model=List[EmployeeCertification])
def route_list_employee_certs(
    employee_id: Optional[str] = None,
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        if _is_rh(current_user):
            return queries.get_employee_certifications(
                cid, employee_id=employee_id, include_archived=include_archived
            )
        my_emp = _employee_scope_id(current_user, cid)
        if not my_emp:
            raise HTTPException(
                status_code=403,
                detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
            )
        return queries.get_employee_certifications(
            cid, employee_id=my_emp, include_archived=include_archived
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{cert_id}", response_model=EmployeeCertification)
def route_get_employee_cert(cert_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_employee_certification(cert_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Habilitation non trouvée.")
        if not _is_rh(current_user):
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp or out.employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("", response_model=EmployeeCertification, status_code=201)
def route_create_employee_cert(
    data: EmployeeCertificationCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_employee_certification(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{cert_id}", response_model=EmployeeCertification)
def route_update_employee_cert(
    cert_id: str,
    data: EmployeeCertificationUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_employee_certification(
            cert_id, _company_id(current_user), data
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{cert_id}/archive", status_code=204)
def route_archive_employee_cert(
    cert_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_employee_certification(cert_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/{cert_id}/upload-certificate", response_model=EmployeeCertification)
async def route_upload_certificate(
    cert_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        body = await file.read()
        if len(body) > MAX_CERT_UPLOAD:
            raise HTTPException(
                status_code=400, detail="Fichier trop volumineux (max 5 Mo)."
            )
        ct = (file.content_type or "").split(";")[0].strip().lower()
        if ct not in ALLOWED_UPLOAD_CT:
            raise HTTPException(
                status_code=400,
                detail="Format non autorisé (PDF, JPG ou PNG uniquement).",
            )
        fname = file.filename or "certificat.pdf"
        return commands.upload_certificate_file(
            _company_id(current_user), cert_id, body, fname
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
