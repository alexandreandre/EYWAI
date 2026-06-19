"""Router API — paramètres prime d'ancienneté entreprise."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.prime_anciennete_settings.application import commands, queries
from app.modules.prime_anciennete_settings.schemas.requests import (
    PrimeAncienneteSettingsUpdate,
)
from app.modules.prime_anciennete_settings.schemas.responses import (
    PrimeAncienneteSettings,
)
from app.modules.users.schemas.responses import User

router = APIRouter(
    prefix="/api/prime-anciennete-settings", tags=["PrimeAncienneteSettings"]
)


def _can_write(user: User, company_id: str) -> bool:
    if user.is_platform_admin:
        return True
    role = user.get_role_in_company(company_id)
    return role in ("admin", "rh")


@router.get("/", response_model=PrimeAncienneteSettings)
def get_prime_anciennete_settings_route(
    current_user: User = Depends(get_current_user),
) -> PrimeAncienneteSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not current_user.has_access_to_company(cid):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    try:
        return queries.get_prime_anciennete_settings(cid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/", response_model=PrimeAncienneteSettings)
def put_prime_anciennete_settings_route(
    body: PrimeAncienneteSettingsUpdate,
    current_user: User = Depends(get_current_user),
) -> PrimeAncienneteSettings:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    cid = str(company_id)
    if not _can_write(current_user, cid):
        raise HTTPException(
            status_code=403,
            detail="Modification réservée aux administrateurs et RH",
        )
    try:
        return commands.save_prime_anciennete_settings(cid, body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
