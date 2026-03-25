"""
Router API repos_compensateur.

Rôle strict : validation des entrées (query params), auth, appel de l'application, format réponse.
Aucune logique métier : tout est délégué à l'application du module.
Comportement HTTP identique à l'ancien router (POST /calculer-credits).
"""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.repos_compensateur.api.dependencies import (
    ReposCompensateurUserContext,
    get_current_user,
)
from app.modules.repos_compensateur.application import calculer_credits_repos_command
from app.modules.repos_compensateur.schemas import CalculerCreditsResponse

router = APIRouter(
    prefix="/api/repos-compensateur",
    tags=["Repos Compensateur"],
)


@router.post("/calculer-credits", response_model=CalculerCreditsResponse)
async def calculer_credits_repos(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
    company_id: str | None = Query(None),
    current_user: ReposCompensateurUserContext = Depends(get_current_user),
) -> CalculerCreditsResponse:
    """
    Calcule les crédits COR pour tous les employés de l'entreprise sur le mois donné.
    Délègue à l'application ; déclenché par la RH ou un cron (jamais depuis le flux de paie).
    """
    target_company_id = company_id or current_user.active_company_id
    if not target_company_id:
        raise HTTPException(status_code=400, detail="company_id requis.")

    try:
        result = calculer_credits_repos_command(
            year=year,
            month=month,
            target_company_id=target_company_id,
        )
        return CalculerCreditsResponse(
            company_id=result.company_id,
            year=result.year,
            month=result.month,
            employees_processed=result.employees_processed,
            credits_created=result.credits_created,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
