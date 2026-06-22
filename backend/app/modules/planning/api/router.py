"""Router API — module Planning (délégation application uniquement)."""

from __future__ import annotations

import traceback
from datetime import date as date_cls
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.security import get_current_user
from app.modules.planning.application import commands, queries as app_queries
from app.modules.planning.schemas.requests import (
    CompanyPlanningSettingsUpdate,
    DayLockRequest,
    ShiftCreate,
    ShiftTypeCreate,
    ShiftTypeUpdate,
    ShiftUpdate,
    WeekDuplicateRequest,
    WeekLockRequest,
    WeekPublishRequest,
)
from app.modules.planning.schemas.responses import ShiftResponse, ShiftResponseRH
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


@router.get("/month", response_model=List[ShiftResponseRH])
async def get_month_planning(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Tous les shifts du mois (entreprise active) — RH uniquement."""
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.list_company_shifts_month_rh(company_id, year, month)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/on-call", response_model=List[ShiftResponseRH])
async def get_on_call_schedule(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Astreintes du mois (transverse_category astreinte ou on_call) — RH uniquement."""
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    today = date_cls.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    try:
        return app_queries.list_company_on_call_month_rh(company_id, y, m)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/on-call", status_code=201)
async def create_on_call_shift(
    data: ShiftCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une astreinte (transverse_category = astreinte)."""
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    if data.shift_type_id:
        raise HTTPException(
            status_code=400,
            detail="Pour une astreinte, ne pas fournir shift_type_id.",
        )
    forced = data.model_copy(
        update={"shift_type_id": None, "transverse_category": "astreinte"}
    )
    try:
        return commands.create_shift(forced, company_id, str(current_user.id))
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replacements", response_model=List[ShiftResponseRH])
async def list_replacements(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Shifts de remplacement du mois — RH uniquement."""
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    today = date_cls.today()
    y = year if year is not None else today.year
    m = month if month is not None else today.month
    try:
        return app_queries.list_company_replacements_month_rh(company_id, y, m)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/replacements", status_code=201, response_model=ShiftResponseRH)
async def create_replacement_shift(
    data: ShiftCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée un shift de remplacement (RH)."""
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    if not data.is_replacement:
        raise HTTPException(
            status_code=400, detail="is_replacement doit être true pour cet endpoint."
        )
    if not data.original_employee_id:
        raise HTTPException(status_code=400, detail="original_employee_id requis.")
    if not data.shift_type_id or data.transverse_category:
        raise HTTPException(
            status_code=400,
            detail="Un remplacement requiert shift_type_id (sans transverse_category).",
        )
    forced = data.model_copy(
        update={
            "is_replacement": True,
            "replacing_employee_id": data.replacing_employee_id or data.employee_id,
        }
    )
    try:
        return commands.create_shift(forced, company_id, str(current_user.id))
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


@router.post("/shift-types", status_code=201)
async def create_shift_type_endpoint(
    body: ShiftTypeCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    from app.modules.planning.application import shift_type_commands

    try:
        payload = body.model_dump(mode="json")
        return shift_type_commands.create_shift_type(company_id, payload)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/shift-types/{shift_type_id}")
async def update_shift_type_endpoint(
    shift_type_id: str,
    body: ShiftTypeUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    from app.modules.planning.application import shift_type_commands

    try:
        payload = body.model_dump(mode="json", exclude_unset=True)
        return shift_type_commands.update_shift_type(
            company_id, shift_type_id, payload
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shift-types/{shift_type_id}")
async def delete_shift_type_endpoint(
    shift_type_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    from app.modules.planning.application import shift_type_commands

    try:
        shift_type_commands.delete_shift_type(company_id, shift_type_id)
        return {"status": "ok"}
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/shift-types/preset/industrial-3x8")
async def apply_industrial_3x8_preset_endpoint(
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    from app.modules.planning.application.preset_shift_teams import (
        apply_industrial_3x8_preset,
    )

    try:
        return apply_industrial_3x8_preset(company_id)
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


@router.get("/me/month", response_model=List[ShiftResponse])
async def get_my_planning_month(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    """Shifts du mois pour le salarié connecté (semaines non brouillon)."""
    company_id = _require_active_company(current_user)
    try:
        return app_queries.list_my_shifts_month(
            str(current_user.id), company_id, year, month
        )
    except HTTPException:
        raise
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
        return app_queries.get_my_planning_week(
            str(current_user.id), company_id, week_start
        )
    except HTTPException:
        raise
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me/export/pdf")
async def export_my_planning_week_pdf(
    week_start: str = Query(..., description="Lundi de la semaine (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
):
    """Export PDF du planning hebdomadaire publié du collaborateur connecté."""
    company_id = _require_active_company(current_user)
    try:
        pdf_bytes = app_queries.build_my_planning_week_pdf(
            str(current_user.id), company_id, week_start
        )
        safe = week_start[:10].replace("/", "-")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="planning-{safe}.pdf"'
            },
        )
    except HTTPException:
        raise
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
