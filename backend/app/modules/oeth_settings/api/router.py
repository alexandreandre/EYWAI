"""Router API paramétrage OETH."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.oeth_settings.application import commands, queries
from app.modules.oeth_settings.schemas.requests import (
    AnnualReviewStatusUpdate,
    BoethExternesUpdate,
    DeductionsUpdate,
    EcapPositionsUpdate,
    EmployeeBoethUpdate,
    OethSettingsUpdate,
    UrssafOverrideUpdate,
)
from app.modules.oeth_settings.schemas.responses import (
    BoethStatusHistoryItem,
    EmployeeBoethProfile,
    OethAnnualReview,
    OethCompliance,
    OethDsnPayload,
    OethSettings,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/oeth-settings", tags=["OethSettings"])


def _can_write(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    return user.get_role_in_company(company_id) in ("admin", "rh")


def _company_id(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(user.active_company_id)
    if not user.has_access_to_company(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé pour cette entreprise")
    return cid


@router.get("/", response_model=OethSettings)
def get_settings(current_user: User = Depends(get_current_user)) -> OethSettings:
    return queries.get_oeth_settings(_company_id(current_user))


@router.put("/", response_model=OethSettings)
def put_settings(
    body: OethSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> OethSettings:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    try:
        return commands.save_oeth_settings(cid, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/compliance", response_model=OethCompliance)
def get_compliance(current_user: User = Depends(get_current_user)) -> OethCompliance:
    return queries.get_compliance(_company_id(current_user))


@router.get("/employees/{employee_id}/boeth", response_model=EmployeeBoethProfile | None)
def get_employee_boeth(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> EmployeeBoethProfile | None:
    return queries.get_employee_boeth(employee_id, _company_id(current_user))


@router.put("/employees/{employee_id}/boeth", response_model=EmployeeBoethProfile)
def put_employee_boeth(
    employee_id: str,
    body: EmployeeBoethUpdate,
    current_user: User = Depends(get_current_user),
) -> EmployeeBoethProfile:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    try:
        return commands.save_employee_boeth(cid, employee_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/employees/{employee_id}/boeth", status_code=204)
def delete_employee_boeth(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    commands.remove_employee_boeth(cid, employee_id)


@router.get(
    "/employees/{employee_id}/boeth/history",
    response_model=list[BoethStatusHistoryItem],
)
def get_employee_boeth_history(
    employee_id: str,
    current_user: User = Depends(get_current_user),
) -> list[BoethStatusHistoryItem]:
    _company_id(current_user)
    return queries.get_employee_boeth_history(employee_id)


@router.get("/annual-reviews/{year}", response_model=OethAnnualReview)
def get_annual_review(
    year: int,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    return queries.get_annual_review(_company_id(current_user), year)


@router.post("/annual-reviews/{year}/compute", response_model=OethAnnualReview)
def compute_annual_review(
    year: int,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    return queries.compute_annual_review(cid, year)


@router.put("/annual-reviews/{year}/urssaf-override", response_model=OethAnnualReview)
def put_urssaf_override(
    year: int,
    body: UrssafOverrideUpdate,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    return commands.save_urssaf_override(cid, year, body)


@router.put("/annual-reviews/{year}/externes", response_model=OethAnnualReview)
def put_externes(
    year: int,
    body: BoethExternesUpdate,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    try:
        return commands.save_boeth_externes(cid, year, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/annual-reviews/{year}/deductions", response_model=OethAnnualReview)
def put_deductions(
    year: int,
    body: DeductionsUpdate,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    try:
        return commands.save_deductions(cid, year, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/annual-reviews/{year}/ecap", response_model=OethAnnualReview)
def put_ecap(
    year: int,
    body: EcapPositionsUpdate,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    return commands.save_ecap_positions(cid, year, body)


@router.put("/annual-reviews/{year}/status", response_model=OethAnnualReview)
def put_review_status(
    year: int,
    body: AnnualReviewStatusUpdate,
    current_user: User = Depends(get_current_user),
) -> OethAnnualReview:
    cid = _company_id(current_user)
    if not _can_write(current_user, cid):
        raise HTTPException(status_code=403, detail="Modification réservée aux administrateurs et RH")
    return commands.update_annual_review_status(cid, year, body)


@router.get("/annual-reviews/{year}/dsn-payload", response_model=OethDsnPayload)
def get_dsn_payload(
    year: int,
    current_user: User = Depends(get_current_user),
) -> OethDsnPayload:
    return queries.build_dsn_payload(_company_id(current_user), year)
