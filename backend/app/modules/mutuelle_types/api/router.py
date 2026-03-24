"""
Router API mutuelle_types.

Délègue toute la logique à l’application du module.
Pas d’accès DB, pas de logique métier : auth + appel application + retour.
Comportement HTTP identique au legacy (chemins, codes, messages).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.mutuelle_types.application.commands import (
    create_mutuelle_type,
    delete_mutuelle_type,
    update_mutuelle_type,
)
from app.modules.mutuelle_types.application.queries import list_mutuelle_types
from app.modules.mutuelle_types.schemas import (
    MutuelleTypeCreate,
    MutuelleTypeUpdate,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Mutuelle Types"])


@router.get("/api/mutuelle-types")
def get_mutuelle_types(
    user: User = Depends(get_current_user),
) -> List[dict]:
    """Liste les formules mutuelle du catalogue de l’entreprise active (avec employee_ids)."""
    if not user.active_company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return list_mutuelle_types(str(user.active_company_id))


@router.post("/api/mutuelle-types", status_code=201)
def create_mutuelle_type_route(
    mutuelle_type: MutuelleTypeCreate,
    user: User = Depends(get_current_user),
) -> dict:
    """Crée une formule de mutuelle. Réservé Admin/RH."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(
            status_code=403,
            detail="Seuls les Admin/RH peuvent créer des formules de mutuelle dans le catalogue",
        )
    return create_mutuelle_type(str(company_id), str(user.id), mutuelle_type)


@router.put("/api/mutuelle-types/{mutuelle_type_id}")
def update_mutuelle_type_route(
    mutuelle_type_id: str,
    mutuelle_type_update: MutuelleTypeUpdate,
    user: User = Depends(get_current_user),
) -> dict:
    """Met à jour une formule de mutuelle. Réservé Admin/RH."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(
            status_code=403,
            detail="Seuls les Admin/RH peuvent modifier des formules de mutuelle",
        )
    return update_mutuelle_type(
        mutuelle_type_id,
        str(company_id),
        str(user.id),
        mutuelle_type_update,
    )


@router.delete("/api/mutuelle-types/{mutuelle_type_id}")
def delete_mutuelle_type_route(
    mutuelle_type_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Supprime une formule de mutuelle. Réservé Admin/RH ou super admin."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not user.is_super_admin and not user.has_rh_access_in_company(
        str(company_id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Seuls les Admin/RH peuvent supprimer des formules de mutuelle",
        )
    return delete_mutuelle_type(mutuelle_type_id, str(company_id))
