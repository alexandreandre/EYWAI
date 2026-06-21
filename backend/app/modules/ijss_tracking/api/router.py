"""Routes API suivi IJSS / CPAM."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.modules.ijss_tracking.application import service
from app.modules.ijss_tracking.schemas.requests import (
    IjssClosePeriodBody,
    IjssImportParseBody,
    IjssImportProfileUpdateBody,
    IjssJustifyBody,
    IjssMatchReceivedBody,
    IjssValidateBody,
)
from app.modules.ijss_tracking.schemas.responses import (
    IjssAbsenceStatus,
    IjssImportPreviewResponse,
    IjssImportProfile,
    IjssPeriodDashboard,
    IjssPeriodSummary,
    IjssDashboardRow,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/ijss-tracking", tags=["Suivi IJSS"])


def _require_rh(user: User) -> str:
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    cid = str(company_id)
    if not user.is_platform_admin and not user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail="Accès réservé aux profils RH.")
    return cid


@router.get("/periods", response_model=IjssPeriodDashboard)
def get_period_dashboard(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
) -> IjssPeriodDashboard:
    cid = _require_rh(current_user)
    try:
        data = service.get_period_dashboard(cid, year, month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return IjssPeriodDashboard(
        period=data["period"],
        summary=IjssPeriodSummary(**data["summary"]),
        rows=[IjssDashboardRow(**r) for r in data["rows"]],
    )


@router.get("/periods/{period_id}", response_model=IjssPeriodDashboard)
def get_period_detail(
    period_id: str,
    current_user: User = Depends(get_current_user),
) -> IjssPeriodDashboard:
    cid = _require_rh(current_user)
    from app.modules.ijss_tracking.infrastructure import repository as repo

    period = repo.get_period(cid, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Période introuvable.")
    data = service.get_period_dashboard(
        cid, int(period["period_year"]), int(period["period_month"])
    )
    return IjssPeriodDashboard(
        period=data["period"],
        summary=IjssPeriodSummary(**data["summary"]),
        rows=[IjssDashboardRow(**r) for r in data["rows"]],
    )


@router.post("/periods/{period_id}/sync-expected")
def sync_expected(
    period_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.sync_expected_lines(cid, period_id)
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/periods/{period_id}/close")
def close_period(
    period_id: str,
    body: IjssClosePeriodBody,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        result = service.close_period(cid, period_id, str(current_user.id))
        if body.notes:
            from app.modules.ijss_tracking.infrastructure import repository as repo

            repo.update_period(period_id, {"notes": body.notes})
        return result
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/periods/{period_id}/sync-cpam")
def sync_cpam(
    period_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.sync_cpam_from_net_entreprises(cid, period_id, str(current_user.id))
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/absences/{absence_id}/ijss", response_model=IjssAbsenceStatus)
def get_absence_ijss(
    absence_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    data = service.get_absence_ijss_status(cid, absence_id)
    return IjssAbsenceStatus(**data)


@router.patch("/received-lines/{line_id}/match")
def match_received_line(
    line_id: str,
    body: IjssMatchReceivedBody,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.match_received_line_manual(
            cid, line_id, body.employee_id, body.expected_line_id
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/expected-lines/{expected_line_id}/validate")
def validate_expected_line(
    expected_line_id: str,
    body: IjssValidateBody,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.validate_expected_line(
            cid,
            expected_line_id,
            str(current_user.id),
            body.amount,
            body.source,
        )
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/expected-lines/{expected_line_id}/apply-to-payslip")
def apply_to_payslip(
    expected_line_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.apply_ijss_to_payslip(
            cid, expected_line_id, str(current_user.id)
        )
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/periods/{period_id}/apply-validated")
def apply_all_validated(
    period_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.apply_all_validated(cid, period_id, str(current_user.id))
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/expected-lines/{expected_line_id}/justify")
def justify_expected_line(
    expected_line_id: str,
    body: IjssJustifyBody,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    return service.justify_variance(
        cid,
        expected_line_id,
        body.content,
        str(current_user.id),
        body.received_line_id,
    )


@router.post("/periods/{period_id}/import/bank", response_model=IjssImportPreviewResponse)
async def import_bank_recap(
    period_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    try:
        result = service.parse_import_file(
            cid,
            period_id,
            "bank_recap",
            file.filename or "import.csv",
            content,
            str(current_user.id),
        )
    except (ValueError, LookupError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IjssImportPreviewResponse(**result)


@router.post("/periods/{period_id}/import/cpam", response_model=IjssImportPreviewResponse)
async def import_cpam_decompte(
    period_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    try:
        result = service.parse_import_file(
            cid,
            period_id,
            "cpam_decompte_file",
            file.filename or "decompte.csv",
            content,
            str(current_user.id),
        )
    except (ValueError, LookupError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return IjssImportPreviewResponse(**result)


@router.post("/import/batches/{batch_id}/commit")
def commit_import_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        return service.commit_import_batch(cid, batch_id)
    except (LookupError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/periods/{period_id}/export-audit")
def export_audit(
    period_id: str,
    current_user: User = Depends(get_current_user),
):
    cid = _require_rh(current_user)
    try:
        xlsx = service.export_audit_excel(cid, period_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="suivi_ijss_audit.xlsx"'},
    )


@router.get("/import-profiles", response_model=list[IjssImportProfile])
def list_import_profiles_route(
    current_user: User = Depends(get_current_user),
) -> list[IjssImportProfile]:
    cid = _require_rh(current_user)
    from app.modules.ijss_tracking.infrastructure import repository as repo

    rows = repo.list_import_profiles(cid)
    return [
        IjssImportProfile(
            id=str(r.get("id")),
            batch_type=str(r.get("batch_type") or ""),
            profile_name=str(r.get("profile_name") or "default"),
            column_mapping=r.get("column_mapping") or {},
        )
        for r in rows
    ]


@router.put("/import-profiles/{batch_type}", response_model=IjssImportProfile)
def upsert_import_profile_route(
    batch_type: str,
    body: IjssImportProfileUpdateBody,
    current_user: User = Depends(get_current_user),
) -> IjssImportProfile:
    cid = _require_rh(current_user)
    if batch_type not in ("bank_recap", "cpam_decompte_file"):
        raise HTTPException(status_code=400, detail="Type d'import invalide.")
    from app.modules.ijss_tracking.infrastructure import repository as repo

    repo.upsert_import_profile(cid, batch_type, body.column_mapping)
    row = repo.get_import_profile(cid, batch_type)
    if not row:
        raise HTTPException(status_code=500, detail="Profil introuvable après mise à jour.")
    return IjssImportProfile(
        id=str(row.get("id")),
        batch_type=str(row.get("batch_type") or batch_type),
        profile_name=str(row.get("profile_name") or "default"),
        column_mapping=row.get("column_mapping") or {},
    )
