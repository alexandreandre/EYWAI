"""Routes API — suivi des taux de prélèvement à la source.

Le fichier est envoyé deux fois : une fois pour l'aperçu, une fois pour
l'application. C'est délibéré. L'alternative — garder l'aperçu côté serveur entre
les deux appels — ferait dépendre une écriture en paie d'un état intermédiaire,
et laisserait le navigateur dicter les taux à écrire. Ici le serveur relit le
fichier et recalcule ce qu'il applique.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.modules.pas_rates.application import exports, ingest, service
from app.modules.pas_rates.schemas.responses import (
    ApercuReponse,
    ApplicationReponse,
    HistoriqueLigne,
    TauxVue,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/pas-rates", tags=["Taux PAS"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Une DSN mensuelle de 250 salariés pèse moins de 2 Mo ; au-delà, le fichier
# n'est pas celui qu'on croit.
TAILLE_MAX = 20 * 1024 * 1024


def _require_rh(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    cid = str(company_id)
    if not current_user.is_platform_admin and not current_user.has_rh_access_in_company(
        cid
    ):
        raise HTTPException(status_code=403, detail="Accès réservé aux profils RH.")
    return cid


def _company_name(current_user: User, company_id: str) -> str:
    for access in current_user.accessible_companies:
        if str(access.company_id) == str(company_id):
            return access.company_name or ""
    return ""


async def _lire_fichier(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    if len(content) > TAILLE_MAX:
        raise HTTPException(
            status_code=400,
            detail="Fichier trop volumineux : 20 Mo au maximum.",
        )
    return content


@router.get("", response_model=TauxVue)
def vue_taux(current_user: User = Depends(get_current_user)) -> TauxVue:
    """Le taux courant de chaque salarié de la société active."""
    cid = _require_rh(current_user)
    data = service.vue_rh(cid, _company_name(current_user, cid))
    return TauxVue(**data)


@router.get("/{employee_id}/historique", response_model=List[HistoriqueLigne])
def historique_taux(
    employee_id: str, current_user: User = Depends(get_current_user)
) -> List[HistoriqueLigne]:
    """Tous les taux reçus pour un salarié, du plus récent au plus ancien."""
    cid = _require_rh(current_user)
    from app.modules.pas_rates.infrastructure import repository as repo

    salarie = repo.get_salarie(employee_id)
    if not salarie or str(salarie.get("company_id")) != cid:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    return [HistoriqueLigne(**row) for row in service.historique(employee_id)]


@router.post("/preview", response_model=ApercuReponse)
async def apercu_fichier(
    file: UploadFile = File(...),
    source: str = Form("dsn"),
    current_user: User = Depends(get_current_user),
) -> ApercuReponse:
    """Ce que le fichier changerait, sans rien écrire."""
    cid = _require_rh(current_user)
    content = await _lire_fichier(file)
    try:
        apercu = ingest.preparer_apercu(
            cid, content, file.filename or "fichier.dsn", source
        )
    except ingest.FichierInvalide as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApercuReponse(**ingest.apercu_to_dict(apercu))


@router.post("/apply", response_model=ApplicationReponse)
async def appliquer_fichier(
    file: UploadFile = File(...),
    source: str = Form("dsn"),
    current_user: User = Depends(get_current_user),
) -> ApplicationReponse:
    """Applique les taux du fichier aux salariés rapprochés."""
    cid = _require_rh(current_user)
    content = await _lire_fichier(file)
    try:
        apercu = ingest.preparer_apercu(
            cid, content, file.filename or "fichier.dsn", source
        )
        resultat = ingest.appliquer(cid, apercu, str(current_user.id))
    except ingest.FichierInvalide as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApplicationReponse(periode=apercu.periode, **resultat)


class TauxManuelRequete(BaseModel):
    taux: float = Field(..., ge=0, le=100)


@router.put("/{employee_id}/taux")
def definir_taux_manuel(
    employee_id: str,
    payload: TauxManuelRequete,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Saisie manuelle du taux par la RH, historisée comme source « manuel »."""
    cid = _require_rh(current_user)
    from app.modules.pas_rates.infrastructure import repository as repo

    salarie = repo.get_salarie(employee_id)
    if not salarie or str(salarie.get("company_id")) != cid:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    try:
        return service.definir_taux_manuel(
            cid, employee_id, payload.taux, str(current_user.id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export_taux(current_user: User = Depends(get_current_user)) -> Response:
    """Export XLSX de l'écran, statut compris."""
    cid = _require_rh(current_user)
    company_name = _company_name(current_user, cid)
    try:
        content, filename = exports.export_taux_pas(cid, company_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de l'export : {exc}"
        ) from exc
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
