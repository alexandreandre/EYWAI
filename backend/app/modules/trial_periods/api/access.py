"""Contrôle d'accès des périodes d'essai : réservé aux profils RH."""

from __future__ import annotations

from fastapi import HTTPException

from app.modules.access_control.application.service import access_control_service
from app.modules.trial_periods.application import queries
from app.modules.users.schemas.responses import User

_ERR_NO_COMPANY = "Aucune entreprise active."
_ERR_RH_REQUIRED = "Accès réservé aux RH et administrateurs."
_ERR_TRIAL_NOT_FOUND = "Période d'essai introuvable."


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


def require_employee_in_company(user: User, company_id: str, employee_id: str) -> None:
    """Le salarié visé appartient à la société active (404 sinon).

    Contrôle de périmètre de `require_employee_access` : on ne révèle pas
    l'existence du salarié. L'administrateur plateforme garde son accès
    transverse.
    """
    if user.is_platform_admin:
        return
    access_control_service.assert_employee_in_company(company_id, employee_id)


def require_trial_period_access(user: User, trial_period_id: str) -> str:
    """RH de la société active, sur une période d'essai d'un salarié de cette société.

    Le dépôt filtre sur l'identifiant seul : sans ce contrôle, une RH de la
    société A modifiait, confirmait ou renouvelait la période d'essai d'un
    salarié de la société B (audit du 25/09/2026, E5). Hors périmètre ou
    introuvable : 404.
    """
    company_id = require_rh_or_admin(user)
    if user.is_platform_admin:
        return company_id
    trial = queries.get_trial_period(trial_period_id)
    if trial is None or str(trial.get("company_id") or "") != company_id:
        raise HTTPException(status_code=404, detail=_ERR_TRIAL_NOT_FOUND)
    require_employee_in_company(user, company_id, str(trial.get("employee_id") or ""))
    return company_id


__all__ = [
    "require_company_id",
    "require_employee_in_company",
    "require_rh_or_admin",
    "require_trial_period_access",
]
