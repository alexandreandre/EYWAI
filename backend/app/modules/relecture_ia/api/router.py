"""Routes de la relecture IA. Lancer : comptes de RELECTURE_IA_COMPTES ; lire : RH de la société."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.relecture_ia.application import service
from app.modules.relecture_ia.schemas.requests import LancerRelectureBody, MarquerVuBody
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/relecture-ia", tags=["Relecture IA"])

_MESSAGE_RESERVE = "La relecture par l'IA est réservée à certains comptes."
_MESSAGE_SOCIETE_ACTIVE = "Choisissez d'abord une société."
_MESSAGE_SANS_ACCES_RH = "Vous n'avez pas accès à la paie de cette société."
_MESSAGE_SOCIETE_REFUSEE = "Une des sociétés cochées n'est pas accessible avec votre compte."
_MESSAGE_SANS_SOCIETE = "Cochez au moins une société."
_MESSAGE_POINT_INTROUVABLE = "Ce point n'existe plus. Rechargez la page."


def _exiger_compte(user: User) -> None:
    if not service.peut_lancer(user.email):
        raise HTTPException(status_code=403, detail=_MESSAGE_RESERVE)


def _exiger_acces_aux_societes(user: User, company_ids: list[str]) -> None:
    if any(not user.has_rh_access_in_company(c) for c in company_ids):
        raise HTTPException(status_code=403, detail=_MESSAGE_SOCIETE_REFUSEE)


def _societe_active_rh(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(status_code=400, detail=_MESSAGE_SOCIETE_ACTIVE)
    if not user.has_rh_access_in_company(user.active_company_id):
        raise HTTPException(status_code=403, detail=_MESSAGE_SANS_ACCES_RH)
    return user.active_company_id


@router.get("/droits")
def lire_droits(user: User = Depends(get_current_user)) -> dict[str, bool]:
    return {"peut_lancer": service.peut_lancer(user.email)}


@router.get("/preparation")
def lire_preparation(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _exiger_compte(user)
    return service.preparer(service.societes_du_compte(user), year, month)


@router.post("/lancer")
def lancer_relecture(
    body: LancerRelectureBody,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _exiger_compte(user)
    _exiger_acces_aux_societes(user, body.company_ids)
    try:
        resultat = service.lancer(
            user.id,
            service.societes_du_compte(user),
            body.year,
            body.month,
            body.company_ids,
            employee_ids=body.employee_ids,
        )
    except service.SansSocieteCochee:
        raise HTTPException(status_code=400, detail=_MESSAGE_SANS_SOCIETE) from None
    except service.SocieteRefusee:
        raise HTTPException(status_code=403, detail=_MESSAGE_SOCIETE_REFUSEE) from None
    if resultat.pop("a_executer"):
        background_tasks.add_task(service.executer, resultat["relecture_id"])
    return resultat


@router.get("/etat")
def lire_etat(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _exiger_compte(user)
    etat = service.lire_etat()
    if etat["a_executer"]:
        background_tasks.add_task(service.executer, etat["relecture"]["id"])
    return {"relecture": etat["relecture"]}


@router.get("/a-regarder")
def lire_a_regarder(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return service.lire_a_regarder(_societe_active_rh(user), year, month)


@router.post("/vus", status_code=204)
def marquer_vu(body: MarquerVuBody, user: User = Depends(get_current_user)) -> None:
    company_id = _societe_active_rh(user)
    try:
        service.marquer_vu(company_id, user.id, body.bulletin_relu_id, body.ligne)
    except service.PointIntrouvable:
        raise HTTPException(status_code=404, detail=_MESSAGE_POINT_INTROUVABLE) from None
