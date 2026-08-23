"""
Router API du module monthly_inputs.

Appelle uniquement la couche application (commands, queries).
Aucune logique métier, aucun accès DB.

SÉCURITÉ : toutes les routes exigent un compte authentifié et travaillent
dans la société ACTIVE de l'appelant — le client Supabase du backend tourne
en service_role, donc rien ici n'est cloisonné par la base : le périmètre
société doit être posé par le code. Les écritures sont réservées au profil
RH ; la lecture par salarié suit la règle des fiches (RH : toute la société,
collaborateur : la sienne).
"""

from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import get_logger
from app.core.security import get_current_user
from app.modules.employees.api.deps import (
    assert_can_read_employee_profile,
    require_rh_access,
)
from app.modules.monthly_inputs.application import commands, queries
from app.modules.monthly_inputs.schemas.requests import (
    MonthlyInput,
    MonthlyInputCreate,
    MonthlyInputUpdate,
)
from app.modules.monthly_inputs.schemas.responses import (
    create_batch_response,
    create_single_response,
    delete_response,
)
from app.modules.users.schemas.responses import User

logger = get_logger("modules.monthly_inputs")

router = APIRouter(tags=["Monthly Inputs"])


def _societe_active(current_user: User) -> str:
    """Société active de l'appelant, sinon 403 (jamais de portée globale)."""
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=403, detail="Impossible de déterminer l'entreprise."
        )
    if not current_user.has_access_to_company(str(company_id)):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé pour cette entreprise."
        )
    return str(company_id)


@router.get("/api/monthly-inputs")
def list_monthly_inputs(
    year: int, month: int, current_user: User = Depends(get_current_user)
):
    """Saisies ponctuelles du mois pour la société active (réservé RH)."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    result = queries.list_monthly_inputs_by_period(year, month, company_id)
    return result.items


@router.post("/api/monthly-inputs", status_code=201)
def create_monthly_inputs(
    payload: List[MonthlyInput], current_user: User = Depends(get_current_user)
):
    """Crée une ou plusieurs saisies mensuelles (réservé RH)."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        result = commands.create_monthly_inputs_batch(payload, company_id)
        return create_batch_response(result.inserted_count)
    except Exception as e:
        logger.exception("create_monthly_inputs")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/monthly-inputs/{input_id}")
def update_monthly_input(
    input_id: str,
    payload: MonthlyInputUpdate,
    current_user: User = Depends(get_current_user),
):
    """Corrige une saisie. La ligne devient prioritaire sur la génération."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        return commands.update_monthly_input(input_id, payload, company_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("update_monthly_input")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/monthly-inputs/{input_id}")
def delete_monthly_input(
    input_id: str, current_user: User = Depends(get_current_user)
):
    """Supprime une saisie ponctuelle (réservé RH, société active)."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    commands.delete_monthly_input(input_id, company_id)
    return delete_response()


@router.get("/api/employees/{employee_id}/monthly-inputs")
def get_employee_monthly_inputs(
    employee_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
):
    """Saisies d'un salarié : RH de la société, ou le salarié lui-même."""
    company_id = _societe_active(current_user)
    assert_can_read_employee_profile(current_user, employee_id, company_id)
    result = queries.list_monthly_inputs_by_employee_period(
        employee_id, year, month, company_id
    )
    return result.items


@router.post("/api/employees/{employee_id}/monthly-inputs", status_code=201)
def create_employee_monthly_inputs(
    employee_id: str,
    prime_data: MonthlyInputCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une saisie ponctuelle pour un salarié (réservé RH)."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        result = commands.create_employee_monthly_input(
            employee_id, prime_data, company_id
        )
        return create_single_response(result.inserted_data)
    except Exception as e:
        logger.exception("create_employee_monthly_inputs")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/employees/{employee_id}/monthly-inputs/{input_id}")
def delete_employee_monthly_input(
    employee_id: str,
    input_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime une saisie ponctuelle d'un salarié (réservé RH)."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        commands.delete_employee_monthly_input(employee_id, input_id, company_id)
        return delete_response()
    except Exception as e:
        logger.exception("delete_employee_monthly_input")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/primes-catalogue")
def get_primes_catalogue(current_user: User = Depends(get_current_user)):
    """Catalogue de primes (payroll_config, config_key='primes')."""
    _societe_active(current_user)
    try:
        return queries.get_primes_catalogue()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
