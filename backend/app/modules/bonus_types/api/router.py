"""
Router API bonus_types : appelle uniquement l'application du module.

Aucune logique métier : validation du corps (schémas), injection contexte user, appel application, format réponse.
Comportement HTTP identique au legacy. Contexte utilisateur via Protocol (aucune dépendance à app.modules.users).
"""
from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.modules.bonus_types.api.dependencies import (
    BonusTypeUserContext,
    get_current_user,
)
from app.modules.bonus_types.application import (
    bonus_type_to_response_dict,
    build_create_input,
    build_update_input,
    calculate_bonus_amount_query,
    create_bonus_type_cmd,
    delete_bonus_type_cmd,
    list_bonus_types_by_company_query,
    update_bonus_type_cmd,
)
from app.modules.bonus_types.schemas import BonusTypeCreate, BonusTypeUpdate

router = APIRouter(tags=["Bonus Types"])


@router.get("/api/bonus-types")
def get_bonus_types(
    user: BonusTypeUserContext = Depends(get_current_user),
) -> List[dict]:
    """Liste les primes du catalogue de l'entreprise active."""
    try:
        items = list_bonus_types_by_company_query(str(user.active_company_id or ""))
        return [bonus_type_to_response_dict(e) for e in items]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des primes: {str(e)}",
        )


@router.post("/api/bonus-types", status_code=201)
def create_bonus_type(
    bonus_type: BonusTypeCreate,
    user: BonusTypeUserContext = Depends(get_current_user),
) -> dict:
    """Crée une prime ; accès RH vérifié dans l'application."""
    try:
        company_id = user.active_company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        input_data = build_create_input(
            bonus_type, str(company_id), str(user.id)
        )
        entity = create_bonus_type_cmd(
            input_data,
            has_rh_access=user.has_rh_access_in_company(str(company_id)),
        )
        return bonus_type_to_response_dict(entity)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la prime: {str(e)}",
        )


@router.put("/api/bonus-types/{bonus_type_id}")
def update_bonus_type(
    bonus_type_id: str,
    bonus_type_update: BonusTypeUpdate,
    user: BonusTypeUserContext = Depends(get_current_user),
) -> dict:
    """Met à jour une prime ; ownership et accès RH vérifiés dans l'application."""
    try:
        company_id = user.active_company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        input_data = build_update_input(bonus_type_update)
        entity = update_bonus_type_cmd(
            bonus_type_id,
            str(company_id),
            user.has_rh_access_in_company(str(company_id)),
            input_data,
        )
        if not entity:
            raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")
        return bonus_type_to_response_dict(entity)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la mise à jour: {str(e)}",
        )


@router.delete("/api/bonus-types/{bonus_type_id}")
def delete_bonus_type(
    bonus_type_id: str,
    user: BonusTypeUserContext = Depends(get_current_user),
) -> dict:
    """Supprime une prime ; ownership et (super_admin ou RH) vérifiés dans l'application."""
    try:
        company_id = user.active_company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        delete_bonus_type_cmd(
            bonus_type_id,
            str(company_id),
            user.is_super_admin,
            user.has_rh_access_in_company(str(company_id)),
        )
        return {"status": "success", "message": "Prime supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la suppression: {str(e)}",
        )


@router.get("/api/bonus-types/calculate/{bonus_type_id}")
def calculate_bonus_amount(
    bonus_type_id: str,
    employee_id: str,
    year: int,
    month: int,
    user: BonusTypeUserContext = Depends(get_current_user),
) -> dict:
    """Calcule le montant d'une prime (montant_fixe ou selon_heures)."""
    try:
        company_id = user.active_company_id
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        result = calculate_bonus_amount_query(
            bonus_type_id,
            str(company_id),
            employee_id,
            year,
            month,
        )
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du calcul: {str(e)}",
        )
