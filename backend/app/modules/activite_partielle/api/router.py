"""Routes de l'activité partielle (réglage de la société, heures chômées du mois)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.modules.activite_partielle.application import service
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/activite-partielle", tags=["Activité partielle"])


def _require_rh(user: User) -> str:
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    cid = str(company_id)
    if not user.is_platform_admin and not user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail="Accès réservé aux profils RH.")
    return cid


class ReglageBody(BaseModel):
    active: bool = False
    date_debut: date | None = None
    date_fin: date | None = None
    taux_indemnite: float = Field(60, gt=0, le=100)
    plancher_horaire: float = Field(9.74, ge=0, le=1000)
    plafond_horaire: float = Field(33.24, gt=0, le=1000)
    heures_par_jour: float | None = Field(None, gt=0, le=24)
    reference_decision: str | None = Field(None, max_length=200)
    note: str | None = Field(None, max_length=2000)


class SaisieHeures(BaseModel):
    employee_id: str
    heures: float = Field(..., ge=0, le=250)


class HeuresDuMoisBody(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    saisies: list[SaisieHeures] = Field(..., min_length=1, max_length=1000)


@router.get("/reglage")
def get_reglage(current_user: User = Depends(get_current_user)):
    return service.lire_reglage(_require_rh(current_user))


@router.put("/reglage")
def put_reglage(body: ReglageBody, current_user: User = Depends(get_current_user)):
    cid = _require_rh(current_user)
    try:
        return service.enregistrer_reglage(cid, body.model_dump(), str(current_user.id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/mois")
def get_mois(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(get_current_user),
):
    return service.lister_mois(_require_rh(current_user), year, month)


@router.post("/mois")
def post_mois(body: HeuresDuMoisBody, current_user: User = Depends(get_current_user)):
    cid = _require_rh(current_user)
    try:
        return service.poser_heures_du_mois(
            cid,
            body.year,
            body.month,
            [s.model_dump() for s in body.saisies],
            str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
