"""Routes REST obligations légales (entretien 2 ans, bilan 6 ans)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.http_dependencies import map_application_exception, require_active_company
from app.core.platform_admin import is_platform_admin
from app.core.security import get_current_user
from app.modules.legal_obligations.application import commands, queries
from app.modules.legal_obligations.schemas.requests import LegalObligationOverrideWrite
from app.modules.legal_obligations.schemas.responses import (
    LegalObligationOverride,
    LegalObligationStatus,
    OverdueCountResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/legal-obligations", tags=["LegalObligations"])


def _company_id(user: User) -> str:
    return require_active_company(user)


def _is_rh(user: User) -> bool:
    if is_platform_admin(user):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


@router.get("", response_model=List[LegalObligationStatus])
def route_list_status(
    status_filter: Optional[str] = Query(
        None, description="Filtre sur professional_interview_status"
    ),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    if status_filter is not None and status_filter not in (
        "overdue",
        "due_soon",
        "up_to_date",
    ):
        raise HTTPException(status_code=400, detail="status_filter invalide.")
    try:
        return queries.get_all_status(_company_id(current_user), status_filter)
    except HTTPException:
        raise
    except Exception as e:
        raise map_application_exception(e) from e


@router.get("/count/overdue", response_model=OverdueCountResponse)
def route_overdue_count(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_overdue_count(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        raise map_application_exception(e) from e


@router.get("/{employee_id}", response_model=LegalObligationStatus)
def route_get_employee_status(employee_id: str, current_user: User = Depends(get_current_user)):
    cid = _company_id(current_user)
    if _is_rh(current_user):
        try:
            return queries.get_employee_status(cid, employee_id)
        except HTTPException:
            raise
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise map_application_exception(e) from e
    scope = _employee_scope_id(current_user, cid)
    if not scope or scope != employee_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        return queries.get_employee_status(cid, employee_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise map_application_exception(e) from e


@router.put("/{employee_id}/override", response_model=LegalObligationOverride)
def route_save_override(
    employee_id: str,
    body: LegalObligationOverrideWrite,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.save_override(
            _company_id(current_user),
            employee_id,
            body,
            str(current_user.id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise map_application_exception(e) from e
