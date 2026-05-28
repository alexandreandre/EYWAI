"""
Router API maintien de salaire.

GET : lecture pour les profils avec accès RH dans l’entreprise active.
PUT : admin, rh ou super_admin uniquement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.maintenance_settings.application import commands, queries
from app.modules.maintenance_settings.schemas.requests import MaintenanceSettingsUpdate
from app.modules.maintenance_settings.schemas.responses import MaintenanceSettings
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/maintenance-settings", tags=["MaintenanceSettings"])


def _can_write_maintenance_settings(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    role = user.get_role_in_company(company_id)
    return role in ("admin", "rh")


@router.get("/", response_model=MaintenanceSettings)
def get_maintenance_settings_route(
    current_user: User = Depends(get_current_user),
) -> MaintenanceSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not current_user.has_access_to_company(cid):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )
    return queries.get_maintenance_settings(cid)


@router.put("/", response_model=MaintenanceSettings)
def put_maintenance_settings_route(
    body: MaintenanceSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> MaintenanceSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not _can_write_maintenance_settings(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Modification réservée aux administrateurs et RH",
        )
    return commands.save_maintenance_settings(cid, body)
