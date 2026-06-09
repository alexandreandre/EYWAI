"""
Router API paramétrage JEI.

GET : lecture pour les profils avec accès à l'entreprise active.
PUT : admin ou rh uniquement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.jei_settings.application import commands, queries
from app.modules.jei_settings.schemas.requests import JeiSettingsUpdate
from app.modules.jei_settings.schemas.responses import JeiSettings
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/jei-settings", tags=["JeiSettings"])


def _can_write_jei_settings(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    role = user.get_role_in_company(company_id)
    return role in ("admin", "rh")


@router.get("/", response_model=JeiSettings)
def get_jei_settings_route(
    current_user: User = Depends(get_current_user),
) -> JeiSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not current_user.has_access_to_company(cid):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )
    return queries.get_jei_settings(cid)


@router.put("/", response_model=JeiSettings)
def put_jei_settings_route(
    body: JeiSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> JeiSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not _can_write_jei_settings(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Modification réservée aux administrateurs et RH",
        )
    try:
        return commands.save_jei_settings(cid, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
