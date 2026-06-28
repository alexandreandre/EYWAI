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
from app.modules.employees.api.deps import resolve_my_employee_id
from app.modules.mutuelle_types.application.commands import (
    create_mutuelle_type,
    delete_mutuelle_type,
    update_mutuelle_type,
)
from app.modules.mutuelle_types.application.employee_choice import (
    assign_employee_mutuelle_choice,
    get_employee_mutuelle_choices,
)
from app.modules.mutuelle_types.application.psc_settings import (
    get_psc_settings,
    upsert_psc_settings,
)
from app.modules.mutuelle_types.application.queries import list_mutuelle_types
from app.modules.mutuelle_types.schemas import (
    MutuelleTypeCreate,
    MutuelleTypeUpdate,
)
from app.modules.mutuelle_types.schemas.psc_settings import (
    EmployeeMutuelleChoiceRequest,
    EmployeeMutuelleChoicesResponse,
    PscSettingsResponse,
    PscSettingsUpdate,
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
    if not user.is_platform_admin and not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(
            status_code=403,
            detail="Seuls les Admin/RH peuvent supprimer des formules de mutuelle",
        )
    return delete_mutuelle_type(mutuelle_type_id, str(company_id))


@router.get("/api/psc-settings", response_model=PscSettingsResponse)
def get_psc_settings_route(user: User = Depends(get_current_user)) -> dict:
    """Paramètres PSC (mutuelle) de l'entreprise active."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return get_psc_settings(str(company_id))


@router.put("/api/psc-settings", response_model=PscSettingsResponse)
def update_psc_settings_route(
    payload: PscSettingsUpdate,
    user: User = Depends(get_current_user),
) -> dict:
    """Met à jour les paramètres PSC. Réservé Admin/RH."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")
    data = payload.model_dump(exclude_unset=True)
    return upsert_psc_settings(str(company_id), **data)


@router.get(
    "/api/me/mutuelle-choices",
    response_model=EmployeeMutuelleChoicesResponse,
)
def get_my_mutuelle_choices(user: User = Depends(get_current_user)) -> dict:
    """(Espace salarié) Formules mutuelle éligibles et sélection courante."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    employee_id = resolve_my_employee_id(user)
    return get_employee_mutuelle_choices(str(company_id), employee_id)


@router.put(
    "/api/me/mutuelle-choice",
    response_model=EmployeeMutuelleChoicesResponse,
)
def set_my_mutuelle_choice(
    payload: EmployeeMutuelleChoiceRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """(Espace salarié) Choisit sa formule mutuelle."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    employee_id = resolve_my_employee_id(user)
    return assign_employee_mutuelle_choice(
        str(company_id),
        employee_id,
        payload.mutuelle_type_id,
        str(user.id),
    )
