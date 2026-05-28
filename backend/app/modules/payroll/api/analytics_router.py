"""Router API — Analytics Paie."""

from __future__ import annotations

import traceback
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.access_control.application.service import access_control_service
from app.modules.payroll.application import analytics_queries
from app.modules.payroll.schemas.analytics_responses import (
    PayrollAnalyticsBreakdown,
    PayrollAnalyticsSummary,
    PayrollAnalyticsTrends,
    PayrollPeriodsResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/payroll", tags=["Analytics Paie"])

from app.modules.payroll.domain.permissions import PAYROLL_ANALYTICS_VIEW


def _require_payroll_analytics_access(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    cid = str(company_id)
    if current_user.is_platform_admin:
        return cid
    role = current_user.get_role_in_company(cid)
    if role in ("admin", "rh", "collaborateur_rh"):
        if current_user.has_rh_access_in_company(cid):
            return cid
    if role == "custom":
        if access_control_service.check_user_has_permission(
            str(current_user.id), cid, PAYROLL_ANALYTICS_VIEW
        ) or access_control_service.has_any_rh_permission(str(current_user.id), cid):
            return cid
    elif current_user.has_rh_access_in_company(cid):
        return cid
    raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")


@router.get("/analytics/summary", response_model=PayrollAnalyticsSummary)
def payroll_analytics_summary(
    period: str = Query(..., description="Période YYYY-MM"),
    team_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_analytics_access(current_user)
    try:
        return analytics_queries.get_payroll_analytics_summary(
            company_id, period, team_ids=team_ids
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors du chargement du résumé paie."
        ) from None


@router.get("/analytics/trends", response_model=PayrollAnalyticsTrends)
def payroll_analytics_trends(
    months: int = Query(12, ge=1, le=24),
    end_period: Optional[str] = Query(None, description="Fin de série YYYY-MM"),
    team_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_analytics_access(current_user)
    try:
        return analytics_queries.get_payroll_analytics_trends(
            company_id,
            months=months,
            end_period=end_period,
            team_ids=team_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors du chargement des tendances paie."
        ) from None


@router.get("/analytics/breakdown", response_model=PayrollAnalyticsBreakdown)
def payroll_analytics_breakdown(
    period: str = Query(..., description="Période YYYY-MM"),
    group_by: Literal["team", "service", "contract_type"] = Query("team"),
    team_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_analytics_access(current_user)
    try:
        return analytics_queries.get_payroll_analytics_breakdown(
            company_id, period, group_by=group_by, team_ids=team_ids
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors du chargement de la répartition paie."
        ) from None


@router.get("/periods", response_model=PayrollPeriodsResponse)
def payroll_periods(
    year: int = Query(..., ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
):
    company_id = _require_payroll_analytics_access(current_user)
    try:
        return analytics_queries.get_payroll_periods(company_id, year)
    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors du chargement des périodes de paie."
        ) from None
