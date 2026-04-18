"""Router API — module Planning (délégation application uniquement)."""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.planning.application import commands, queries as app_queries
from app.modules.planning.infrastructure.repository import planning_repository
from app.modules.planning.schemas.requests import (
    CompanyPlanningSettingsUpdate,
    DayLockRequest,
    ShiftCreate,
    ShiftUpdate,
    WeekDuplicateRequest,
    WeekLockRequest,
    WeekPublishRequest,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/planning", tags=["Planning"])


def _handle_application_errors(e: Exception) -> None:
    """ValueError → 400, LookupError → 404, PermissionError → 403, RuntimeError → 500."""
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=500, detail=str(e))
    raise


def _require_active_company(current_user: User) -> str:
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Entreprise active requise.")
    return str(cid)


def _require_rh(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au RH / admin.")


@router.get("/week")
async def get_week_planning(
    week_start: str = Query(..., description="Lundi de la semaine (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_week_planning(company_id, week_start, is_rh=True)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shifts", status_code=201)
async def create_shift_endpoint(
    data: ShiftCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.create_shift(data, company_id, str(current_user.id))
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/shifts/{shift_id}")
async def update_shift_endpoint(
    shift_id: str,
    data: ShiftUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.update_shift(shift_id, data, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shifts/{shift_id}", status_code=204)
async def delete_shift_endpoint(
    shift_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        commands.delete_shift(shift_id, company_id)
        return Response(status_code=204)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/week/lock", status_code=200)
async def lock_week_endpoint(
    data: WeekLockRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.lock_week(data, company_id, str(current_user.id))
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/week/unlock", status_code=200)
async def unlock_week_endpoint(
    data: WeekLockRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.unlock_week(
            data.week_start.isoformat(),
            company_id,
            str(current_user.id),
            data.reason,
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/day/lock", status_code=200)
async def lock_day_endpoint(
    data: DayLockRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.lock_day(data, company_id, str(current_user.id))
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/day/unlock", status_code=200)
async def unlock_day_endpoint(
    data: DayLockRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.unlock_day(
            data.day_date.isoformat(),
            company_id,
            str(current_user.id),
            data.reason,
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/week/publish", status_code=200)
async def publish_week_endpoint(
    data: WeekPublishRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.publish_week(data, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/week/duplicate", status_code=200)
async def duplicate_week_endpoint(
    data: WeekDuplicateRequest,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.duplicate_week(data, company_id, str(current_user.id))
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lock-history")
async def get_lock_history_endpoint(current_user: User = Depends(get_current_user)):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_lock_history(company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shifts/{shift_id}")
async def get_shift_detail_endpoint(
    shift_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_shift_detail(shift_id, company_id, is_rh=True)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shift-types")
async def get_shift_types_endpoint(current_user: User = Depends(get_current_user)):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_shift_types_for_company(company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings")
async def get_settings_endpoint(current_user: User = Depends(get_current_user)):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_company_settings(company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/settings")
async def patch_settings_endpoint(
    data: CompanyPlanningSettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.update_company_settings(data, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_my_planning_week(
    week_start: str = Query(..., description="Lundi de la semaine (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    try:
        r = (
            supabase.table("employees")
            .select("id")
            .eq("user_id", str(current_user.id))
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        employee = r.data if r else None
        if not employee or not employee.get("id"):
            raise HTTPException(
                status_code=404, detail="Profil salarié introuvable pour cette entreprise."
            )
        employee_id = str(employee["id"])
        ws = week_start[:10]
        wstatus = planning_repository.get_week_status(company_id, ws)
        team_view = bool(wstatus.get("team_view_enabled")) if wstatus else False
        return app_queries.get_employee_planning(employee_id, ws, team_view)
    except HTTPException:
        raise
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
