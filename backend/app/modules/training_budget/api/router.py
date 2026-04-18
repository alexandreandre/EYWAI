"""Routes REST budget formation."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.training_budget.application import commands, queries
from app.modules.training_budget.schemas.requests import TrainingBudgetPutBody
from app.modules.training_budget.schemas.responses import TrainingBudgetWithConsumption
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/training-budget", tags=["TrainingBudget"])


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


@router.get("", response_model=List[TrainingBudgetWithConsumption])
def route_list_budgets(current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_all_budgets(_company_id(current_user))
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/{year}", response_model=TrainingBudgetWithConsumption)
def route_get_budget(year: int, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_budget(_company_id(current_user), year)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.put("/{year}", response_model=TrainingBudgetWithConsumption)
def route_put_budget(
    year: int,
    body: TrainingBudgetPutBody,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.save_budget(_company_id(current_user), year, body)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)
