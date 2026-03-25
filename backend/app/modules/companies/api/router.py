"""
Router API du module companies.

Délègue toute la logique à la couche application (queries, commands, service).
Aucune logique métier ni accès DB : validation, résolution contexte, appel application, retour HTTP.
Comportement HTTP identique à api/routers/company.py.
"""

import traceback

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.companies.application import commands, queries
from app.modules.users.schemas.responses import User
from app.modules.companies.application.service import (
    resolve_company_id_for_details,
    resolve_company_id_for_user,
)
from app.modules.companies.schemas.requests import CompanySettingsUpdate
from app.modules.companies.schemas.responses import (
    CompanyDetailsResponse,
    CompanySettingsResponse,
)

router = APIRouter(tags=["Company"])


@router.get("/details", response_model=CompanyDetailsResponse)
def get_company_details_and_kpis(
    current_user: User = Depends(get_current_user),
):
    """
    Récupère les détails complets de l'entreprise de l'utilisateur connecté
    ainsi que des indicateurs de performance clés (KPIs) avancés pour le dashboard de pilotage.
    """
    try:
        company_id = resolve_company_id_for_details(current_user)
        if not company_id:
            raise HTTPException(
                status_code=403,
                detail="Impossible de déterminer l'entreprise de l'utilisateur.",
            )
        result = queries.get_company_details_and_kpis(company_id, current_user)
        return CompanyDetailsResponse(
            company_data=result.company_data,
            kpis=result.kpis,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR: Exception dans get_company_details_and_kpis:")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


@router.get("/settings", response_model=CompanySettingsResponse)
def get_company_settings(
    current_user: User = Depends(get_current_user),
):
    """
    Récupère les paramètres (settings) de l'entreprise active.
    Utilisé notamment pour savoir si le module suivi médical est activé.
    """
    company_id = resolve_company_id_for_user(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    try:
        result = queries.get_company_settings(company_id, current_user)
        return CompanySettingsResponse(
            medical_follow_up_enabled=result.medical_follow_up_enabled,
            settings=result.settings,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/settings", response_model=CompanySettingsResponse)
def update_company_settings(
    body: CompanySettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Met à jour les paramètres de l'entreprise active (ex: activation du module suivi médical).
    Réservé aux utilisateurs admin ou RH selon politique.
    """
    company_id = resolve_company_id_for_user(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Droits insuffisants pour modifier les paramètres",
        )
    try:
        result = commands.update_company_settings(
            company_id,
            body.to_settings_delta(),
            current_user,
        )
        return CompanySettingsResponse(
            medical_follow_up_enabled=result.medical_follow_up_enabled,
            settings=result.settings,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
