"""
Router API du module residence_permits.

Appelle uniquement l'application du module. Aucune logique métier ni accès DB dans le router.
Comportement HTTP identique à api/routers/residence_permits (GET /api/residence-permits).

Dépendances app uniquement : app.core.security, app.modules.users (User). Aucun import legacy.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.residence_permits.application.queries import get_residence_permits_list
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/residence-permits", tags=["Residence Permits"])


def _require_rh_company_context(current_user: User) -> str:
    """Entreprise active + accès RH ; lève 400 ou 403 sinon."""
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return str(company_id)


@router.get("", response_model=List[ResidencePermitListItem])
def get_residence_permits_list_route(
    current_user: User = Depends(get_current_user),
):
    """
    Liste des salariés soumis au titre de séjour pour l'entreprise active.
    Filtre : is_subject_to_residence_permit=true, employment_status in ('actif','en_sortie').
    """
    company_id = _require_rh_company_context(current_user)
    try:
        return get_residence_permits_list(company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la récupération des titres de séjour: {str(e)}",
        )
