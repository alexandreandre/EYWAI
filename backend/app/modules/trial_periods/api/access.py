"""Contrôle d'accès des périodes d'essai : réservé aux profils RH."""

from __future__ import annotations

from fastapi import HTTPException

from app.modules.users.schemas.responses import User

_ERR_NO_COMPANY = "Aucune entreprise active."
_ERR_RH_REQUIRED = "Accès réservé aux RH et administrateurs."


def require_company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail=_ERR_NO_COMPANY)
    if not user.has_access_to_company(cid):
        raise HTTPException(status_code=403, detail="Accès refusé à cette entreprise.")
    return str(cid)


def require_rh_or_admin(user: User) -> str:
    cid = require_company_id(user)
    if user.is_platform_admin:
        return cid
    if not user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail=_ERR_RH_REQUIRED)
    return cid


__all__ = ["require_company_id", "require_rh_or_admin"]
