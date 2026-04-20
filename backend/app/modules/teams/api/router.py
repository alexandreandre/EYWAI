"""Router API — module Équipes."""

from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.security import get_current_user
from app.modules.teams.application import commands, queries as app_queries
from app.modules.teams.schemas.requests import (
    AssignEmployeeTeamBody,
    TeamCreate,
    TeamUpdate,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/teams", tags=["Teams"])


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


@router.get("")
async def list_teams(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_teams(company_id, include_archived)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.post("", status_code=201)
async def create_team_endpoint(
    data: TeamCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.create_team(data, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.get("/analytics")
async def team_analytics_endpoint(
    period_start: str = Query(..., description="Début (YYYY-MM-DD)"),
    period_end: str = Query(..., description="Fin (YYYY-MM-DD)"),
    team_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_team_analytics(
            company_id, period_start, period_end, team_ids
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.get("/check-name")
async def check_team_name_endpoint(
    name: str = Query(..., min_length=1),
    exclude_team_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.check_team_name_available(
            company_id, name, exclude_team_id
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.patch("/employees/{employee_id}/team")
async def assign_employee_team_endpoint(
    employee_id: str,
    body: AssignEmployeeTeamBody,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.assign_employee_to_team(
            employee_id, body.team_id, company_id
        )
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.get("/{team_id}")
async def get_team_endpoint(
    team_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return app_queries.get_team_detail(team_id, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.patch("/{team_id}")
async def update_team_endpoint(
    team_id: str,
    data: TeamUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.update_team(team_id, data, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.post("/{team_id}/archive")
async def archive_team_endpoint(
    team_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.archive_team(team_id, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.post("/{team_id}/reactivate")
async def reactivate_team_endpoint(
    team_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        return commands.reactivate_team(team_id, company_id)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")


@router.delete("/{team_id}", status_code=204)
async def delete_team_endpoint(
    team_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _require_active_company(current_user)
    _require_rh(current_user, company_id)
    try:
        commands.delete_team(team_id, company_id)
        return Response(status_code=204)
    except (ValueError, LookupError, PermissionError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Erreur serveur.")
