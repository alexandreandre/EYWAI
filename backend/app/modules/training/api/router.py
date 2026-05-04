"""Routes REST catalogue formations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.core.security import get_current_user
from app.modules.training.application import commands, queries
from app.modules.training.infrastructure.repository import training_repository
from app.modules.training.schemas.requests import (
    EnrollmentRequestBySalarie,
    ManagerApprovalRequest,
    RHApprovalRequest,
    TrainingCatalogCreate,
    TrainingCatalogUpdate,
    TrainingEnrollmentCreate,
    TrainingEnrollmentUpdate,
    TrainingEvaluationRequest,
)
from app.modules.training.schemas.responses import (
    CertificateUploadResponse,
    TotalConsumedResponse,
    TrainingCatalog,
    TrainingEnrollment,
    TrainingEvaluationSummaryItem,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/training", tags=["Training"])


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
    if getattr(user, "is_super_admin", False):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


def _can_manager_act_on_enrollment(
    user: User, enrollment_row: Dict[str, Any], company_id: str
) -> bool:
    if _is_rh(user):
        return True
    my_emp = _employee_scope_id(user, company_id)
    mid = enrollment_row.get("manager_id")
    if not my_emp or not mid:
        return False
    return str(mid) == str(my_emp)


def _can_access_enrollment_eval_or_cert(
    user: User, enrollment_row: Dict[str, Any], company_id: str
) -> bool:
    if _is_rh(user):
        return True
    my_emp = _employee_scope_id(user, company_id)
    return my_emp is not None and str(enrollment_row.get("employee_id")) == str(my_emp)


@router.get("/consumed/{year}", response_model=TotalConsumedResponse)
def route_consumed(year: int, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        total = queries.get_total_consumed(_company_id(current_user), year)
        return TotalConsumedResponse(year=year, total_ht=total)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get(
    "/evaluations/summary",
    response_model=List[TrainingEvaluationSummaryItem],
)
def route_evaluations_summary(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_evaluations_summary(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/catalog", response_model=List[TrainingCatalog])
def route_list_catalog(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
):
    try:
        return queries.get_trainings(_company_id(current_user), include_archived=include_archived)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/catalog/{training_id}", response_model=TrainingCatalog)
def route_get_catalog(training_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_training(training_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Formation non trouvée.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/catalog", response_model=TrainingCatalog, status_code=201)
def route_create_catalog(
    data: TrainingCatalogCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_training(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/catalog/{training_id}", response_model=TrainingCatalog)
def route_update_catalog(
    training_id: str,
    data: TrainingCatalogUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_training(training_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/catalog/{training_id}/archive", status_code=204)
def route_archive_catalog(
    training_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_training(training_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/enrollments", response_model=List[TrainingEnrollment])
def route_list_enrollments(
    training_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        if _is_rh(current_user):
            return queries.get_enrollments(
                cid,
                training_id=training_id,
                employee_id=employee_id,
                status=status,
            )
        my_emp = _employee_scope_id(current_user, cid)
        if not my_emp:
            raise HTTPException(
                status_code=403,
                detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
            )
        if not employee_id or employee_id != my_emp:
            raise HTTPException(status_code=403, detail="Accès non autorisé.")
        return queries.get_enrollments(
            cid,
            training_id=training_id,
            employee_id=my_emp,
            status=status,
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get(
    "/enrollments/pending-manager-approval",
    response_model=List[TrainingEnrollment],
)
def route_pending_manager_approval(current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        if _is_rh(current_user):
            rows = training_repository.list_pending_manager_approval(cid, None)
        else:
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp:
                raise HTTPException(
                    status_code=403,
                    detail="Profil collaborateur introuvable pour cette entreprise.",
                )
            rows = training_repository.list_pending_manager_approval(cid, my_emp)
        return [queries.training_enrollment_from_row(dict(x)) for x in rows]
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get(
    "/enrollments/pending-rh-approval",
    response_model=List[TrainingEnrollment],
)
def route_pending_rh_approval(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        rows = training_repository.list_pending_rh_approval(cid)
        return [queries.training_enrollment_from_row(dict(x)) for x in rows]
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments/request", response_model=TrainingEnrollment, status_code=201)
def route_enrollment_request(
    data: EnrollmentRequestBySalarie,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    emp = _employee_scope_id(current_user, cid)
    if not emp:
        raise HTTPException(
            status_code=403,
            detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
        )
    try:
        row = training_repository.create_enrollment_request(
            emp,
            cid,
            data.training_id,
            str(current_user.id),
            data.preferred_date.isoformat() if data.preferred_date else None,
            data.motivation,
        )
        return queries.training_enrollment_from_row(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/enrollments/{enrollment_id}", response_model=TrainingEnrollment)
def route_get_enrollment(enrollment_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    try:
        out = queries.get_enrollment(enrollment_id, cid)
        if out is None:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if not _is_rh(current_user):
            my_emp = _employee_scope_id(current_user, cid)
            if not my_emp or out.employee_id != my_emp:
                raise HTTPException(status_code=403, detail="Accès refusé.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments", response_model=TrainingEnrollment, status_code=201)
def route_create_enrollment(
    data: TrainingEnrollmentCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_enrollment(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/enrollments/{enrollment_id}", response_model=TrainingEnrollment)
def route_update_enrollment(
    enrollment_id: str,
    data: TrainingEnrollmentUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_enrollment(enrollment_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments/{enrollment_id}/cancel", status_code=204)
def route_cancel_enrollment(
    enrollment_id: str, current_user: User = Depends(get_current_user)
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.cancel_enrollment(enrollment_id, _company_id(current_user))
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post(
    "/enrollments/{enrollment_id}/manager-approve",
    response_model=TrainingEnrollment,
)
def route_manager_approve(
    enrollment_id: str,
    body: ManagerApprovalRequest,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        row = training_repository.get_enrollment_by_id(enrollment_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if str(row.get("status") or "") != "demande_salarie":
            raise HTTPException(
                status_code=400,
                detail="Cette inscription n'est pas en attente de validation manager.",
            )
        if not _can_manager_act_on_enrollment(current_user, row, cid):
            raise HTTPException(status_code=403, detail="Accès refusé.")
        updated = training_repository.approve_by_manager(
            enrollment_id,
            cid,
            body.approved,
            body.rejection_reason,
        )
        return queries.training_enrollment_from_row(dict(updated))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/enrollments/{enrollment_id}/rh-approve", response_model=TrainingEnrollment)
def route_rh_approve(
    enrollment_id: str,
    body: RHApprovalRequest,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        row = training_repository.get_enrollment_by_id(enrollment_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if str(row.get("status") or "") != "approuve_manager":
            raise HTTPException(
                status_code=400,
                detail="Cette inscription n'est pas en attente de validation RH.",
            )
        updated = training_repository.approve_by_rh(
            enrollment_id,
            cid,
            body.approved,
            body.rejection_reason,
            body.planned_start_date.isoformat() if body.planned_start_date else None,
            body.planned_end_date.isoformat() if body.planned_end_date else None,
        )
        return queries.training_enrollment_from_row(dict(updated))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


_MAX_TRAINING_CERT_UPLOAD = 5 * 1024 * 1024
_ALLOWED_TRAINING_CERT_CT = frozenset(
    {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
)


@router.post("/enrollments/{enrollment_id}/evaluate", response_model=TrainingEnrollment)
def route_submit_evaluation(
    enrollment_id: str,
    data: TrainingEvaluationRequest,
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        row = training_repository.get_enrollment_by_id(enrollment_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if not _can_access_enrollment_eval_or_cert(current_user, row, cid):
            raise HTTPException(status_code=403, detail="Accès refusé.")
        actor: Optional[str] = None
        if not _is_rh(current_user):
            actor = _employee_scope_id(current_user, cid)
            if not actor:
                raise HTTPException(
                    status_code=403,
                    detail="Profil collaborateur introuvable pour cette entreprise.",
                )
        updated = training_repository.submit_evaluation(
            enrollment_id,
            cid,
            actor,
            data.rating,
            data.comment,
        )
        return queries.training_enrollment_from_row(dict(updated))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post(
    "/enrollments/{enrollment_id}/upload-certificate",
    response_model=CertificateUploadResponse,
)
async def route_upload_enrollment_certificate(
    enrollment_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    try:
        row = training_repository.get_enrollment_by_id(enrollment_id, cid)
        if not row:
            raise HTTPException(status_code=404, detail="Inscription non trouvée.")
        if not _can_access_enrollment_eval_or_cert(current_user, row, cid):
            raise HTTPException(status_code=403, detail="Accès refusé.")
        body = await file.read()
        if len(body) > _MAX_TRAINING_CERT_UPLOAD:
            raise HTTPException(
                status_code=400, detail="Fichier trop volumineux (max 5 Mo)."
            )
        ct = (file.content_type or "").split(";")[0].strip().lower()
        if ct not in _ALLOWED_TRAINING_CERT_CT:
            raise HTTPException(
                status_code=400,
                detail="Format non autorisé (PDF, JPG ou PNG uniquement).",
            )
        fname = file.filename or "certificat.pdf"
        url = training_repository.upload_enrollment_certificate(
            enrollment_id, cid, body, fname, ct
        )
        return CertificateUploadResponse(certificate_url=url)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
