"""
Router API du module dashboard.

Appelle uniquement l'application du module (queries). Résolution du contexte
(user, entreprise active, accès RH) puis délégation ; aucune logique métier.
Comportement HTTP identique au router legacy.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User
from app.modules.dashboard.application import queries
from app.modules.dashboard.schemas.responses import DashboardData, ResidencePermitStats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _require_rh_company_context(current_user: User) -> str:
    """
    Retourne l'entreprise active si l'utilisateur a un accès RH.
    Sinon lève HTTPException (400 ou 403).
    """
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return str(company_id)


@router.get("/all", response_model=DashboardData)
def get_dashboard_data_route(
    current_user: User = Depends(get_current_user),
):
    """Récupère toutes les données du cockpit RH pour l'entreprise active."""
    company_id = _require_rh_company_context(current_user)
    try:
        return queries.get_dashboard_data(company_id)
    except Exception as e:
        logging.error(
            "Erreur lors de la récupération des données du dashboard: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


@router.get("/residence-permit-stats", response_model=ResidencePermitStats)
def get_residence_permit_stats_route(
    current_user: User = Depends(get_current_user),
):
    """Retourne les statistiques agrégées des titres de séjour pour le dashboard RH."""
    company_id = _require_rh_company_context(current_user)
    return queries.get_residence_permit_stats(company_id)
