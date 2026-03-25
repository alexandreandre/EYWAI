"""
Router API du module promotions.

Appelle uniquement la couche application du module. Aucune logique métier :
validation des entrées (schémas), garde-fous d'accès (dependencies), délégation à l'application.
Comportement HTTP identique au router legacy (préfixe, routes, codes, modèles de réponse).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.modules.users.schemas.responses import User
from app.modules.promotions.api.dependencies import (
    can_approve_reject,
    get_company_id_required,
    get_current_user,
    require_rh,
)
from app.modules.promotions.application import (
    approve_promotion_cmd,
    create_promotion_cmd,
    delete_promotion_cmd,
    get_promotion_by_id_query,
    get_promotion_document_stream_query,
    get_promotion_stats_query,
    list_promotions_query,
    mark_effective_promotion_cmd,
    reject_promotion_cmd,
    submit_promotion_cmd,
    update_promotion_cmd,
)
from app.modules.promotions.schemas import (
    PromotionApprove,
    PromotionCreate,
    PromotionListItem,
    PromotionRead,
    PromotionReject,
    PromotionStats,
    PromotionUpdate,
)

router = APIRouter(
    prefix="/api/promotions",
    tags=["Promotions"],
)


# ---------------------------------------------------------------------------
# GET /api/promotions
# ---------------------------------------------------------------------------
@router.get("", response_model=List[PromotionListItem])
def list_promotions(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    employee_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=500),
    offset: Optional[int] = Query(None, ge=0),
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Liste les promotions de l'entreprise active avec filtres. Rôle RH requis."""
    return list_promotions_query(
        company_id=company_id,
        year=year,
        status=status,
        promotion_type=type,
        employee_id=employee_id,
        search=search,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/promotions/stats
# ---------------------------------------------------------------------------
@router.get("/stats", response_model=PromotionStats)
def promotion_stats(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Statistiques des promotions. Rôle RH requis."""
    return get_promotion_stats_query(company_id=company_id, year=year)


# ---------------------------------------------------------------------------
# GET /api/promotions/{promotion_id}
# ---------------------------------------------------------------------------
@router.get("/{promotion_id}", response_model=PromotionRead)
def get_promotion(
    promotion_id: str,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Détail d'une promotion. Rôle RH requis."""
    return get_promotion_by_id_query(promotion_id=promotion_id, company_id=company_id)


# ---------------------------------------------------------------------------
# POST /api/promotions
# ---------------------------------------------------------------------------
@router.post("", response_model=PromotionRead, status_code=201)
def create_promotion_endpoint(
    body: PromotionCreate,
    current_user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Crée une nouvelle promotion. Rôle RH requis."""
    return create_promotion_cmd(
        body=body,
        company_id=company_id,
        requested_by=str(current_user.id),
    )


# ---------------------------------------------------------------------------
# PUT /api/promotions/{promotion_id}
# ---------------------------------------------------------------------------
@router.put("/{promotion_id}", response_model=PromotionRead)
def update_promotion_endpoint(
    promotion_id: str,
    body: PromotionUpdate,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Met à jour une promotion (brouillon ou en attente). Rôle RH requis."""
    return update_promotion_cmd(
        promotion_id=promotion_id,
        body=body,
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# POST /api/promotions/{promotion_id}/submit
# ---------------------------------------------------------------------------
@router.post("/{promotion_id}/submit", response_model=PromotionRead)
def submit_promotion_endpoint(
    promotion_id: str,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Soumet une promotion (draft → pending_approval). Rôle RH requis."""
    return submit_promotion_cmd(promotion_id=promotion_id, company_id=company_id)


# ---------------------------------------------------------------------------
# POST /api/promotions/{promotion_id}/approve
# ---------------------------------------------------------------------------
@router.post("/{promotion_id}/approve", response_model=PromotionRead)
def approve_promotion_endpoint(
    promotion_id: str,
    body: PromotionApprove,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id_required),
):
    """Approuve une promotion. Réservé aux admin et super_admin."""
    if not can_approve_reject(current_user, company_id):
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent approuver une promotion.",
        )
    return approve_promotion_cmd(
        promotion_id=promotion_id,
        company_id=company_id,
        approved_by=str(current_user.id),
        notes=body.notes,
    )


# ---------------------------------------------------------------------------
# POST /api/promotions/{promotion_id}/reject
# ---------------------------------------------------------------------------
@router.post("/{promotion_id}/reject", response_model=PromotionRead)
def reject_promotion_endpoint(
    promotion_id: str,
    body: PromotionReject,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_company_id_required),
):
    """Rejette une promotion. Réservé aux admin et super_admin."""
    if not can_approve_reject(current_user, company_id):
        raise HTTPException(
            status_code=403,
            detail="Seuls les administrateurs peuvent rejeter une promotion.",
        )
    return reject_promotion_cmd(
        promotion_id=promotion_id,
        company_id=company_id,
        rejection_reason=body.rejection_reason,
    )


# ---------------------------------------------------------------------------
# POST /api/promotions/{promotion_id}/mark-effective
# ---------------------------------------------------------------------------
@router.post("/{promotion_id}/mark-effective", response_model=PromotionRead)
def mark_effective_endpoint(
    promotion_id: str,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Marque une promotion comme effective et applique les changements. Rôle RH requis."""
    return mark_effective_promotion_cmd(
        promotion_id=promotion_id,
        company_id=company_id,
    )


# ---------------------------------------------------------------------------
# DELETE /api/promotions/{promotion_id}
# ---------------------------------------------------------------------------
@router.delete("/{promotion_id}", status_code=204)
def delete_promotion_endpoint(
    promotion_id: str,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Supprime une promotion (brouillon uniquement). Rôle RH requis."""
    delete_promotion_cmd(promotion_id=promotion_id, company_id=company_id)


# ---------------------------------------------------------------------------
# GET /api/promotions/{promotion_id}/document
# ---------------------------------------------------------------------------
@router.get("/{promotion_id}/document")
def get_promotion_document(
    promotion_id: str,
    _user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
):
    """Télécharge le document PDF de la promotion. Rôle RH requis."""
    try:
        stream = get_promotion_document_stream_query(
            promotion_id=promotion_id,
            company_id=company_id,
        )
        return StreamingResponse(
            stream,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="promotion_{promotion_id}.pdf"'
            },
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail="Téléchargement du document non implémenté.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=(
                404
                if "non trouvée" in str(e).lower() or "non disponible" in str(e).lower()
                else 500
            ),
            detail=str(e),
        )
