"""Routes des formules de prévoyance de la société active (sur le modèle de /api/mutuelle-types)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.prevoyance_formules.application import service
from app.modules.prevoyance_formules.schemas import FormuleCreate, FormuleUpdate
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Formules de prévoyance"])

_RESERVE_RH = "Seuls les Admin/RH peuvent modifier les formules de prévoyance de la société."


def _http(appel, *args):
    try:
        return appel(*args)
    except service.FormuleErreur as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _societe(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(user.active_company_id)


def _societe_rh(user: User) -> str:
    company_id = _societe(user)
    if not user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail=_RESERVE_RH)
    return company_id


@router.get("/api/prevoyance-formules")
def lister(user: User = Depends(get_current_user)) -> list[dict]:
    return _http(service.lister_formules, _societe(user))


@router.post("/api/prevoyance-formules", status_code=201)
def creer(donnees: FormuleCreate, user: User = Depends(get_current_user)) -> dict:
    return _http(service.creer_formule, _societe_rh(user), str(user.id), donnees)


@router.put("/api/prevoyance-formules/{formule_id}")
def modifier(formule_id: str, donnees: FormuleUpdate, user: User = Depends(get_current_user)) -> dict:
    return _http(service.modifier_formule, formule_id, _societe_rh(user), donnees)


@router.delete("/api/prevoyance-formules/{formule_id}")
def retirer(formule_id: str, user: User = Depends(get_current_user)) -> dict:
    return _http(service.retirer_formule, formule_id, _societe_rh(user))


@router.post("/api/prevoyance-formules/{formule_id}/appliquer")
def appliquer(formule_id: str, user: User = Depends(get_current_user)) -> dict:
    return {"fiches_mises_a_jour": _http(service.appliquer_formule_aux_fiches, formule_id, _societe_rh(user))}
