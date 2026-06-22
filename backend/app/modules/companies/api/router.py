"""
Router API du module companies.

Délègue toute la logique à la couche application (queries, commands, service).
Aucune logique métier ni accès DB : validation, résolution contexte, appel application, retour HTTP.
Comportement HTTP identique à api/routers/company.py.
"""
from app.core.logging import get_logger

logger = get_logger("modules.companies.api.router")


from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.core.security import get_current_user
from app.modules.companies.application import commands, queries
from app.modules.users.schemas.responses import User
from app.modules.companies.application.service import resolve_company_id_for_user
from app.modules.companies.application.export import build_company_export_csv
from app.modules.companies.schemas.requests import (
    CompanyDetailsUpdate,
    CompanySettingsUpdate,
)
from app.modules.companies.schemas.responses import (
    CompanyDetailsResponse,
    CompanyOverviewResponse,
    CompanySettingsResponse,
)

router = APIRouter(tags=["Company"])


@router.get("/details", response_model=CompanyDetailsResponse)
def get_company_details_and_kpis(
    current_user: User = Depends(get_current_user),
):
    """
    Récupère les détails complets de l'entreprise active
    ainsi que des indicateurs de performance clés (KPIs) pour Mon Entreprise.
    """
    try:
        company_id = resolve_company_id_for_user(current_user)
        if not company_id:
            raise HTTPException(status_code=400, detail="Aucune entreprise active")
        if not current_user.has_access_to_company(company_id):
            raise HTTPException(
                status_code=403,
                detail="Accès non autorisé pour cette entreprise",
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
        logger.warning('ERROR: Exception dans get_company_details_and_kpis:')
        logger.exception("Exception")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne du serveur: {str(e)}",
        )


@router.get("/overview", response_model=CompanyOverviewResponse)
def get_company_overview(current_user: User = Depends(get_current_user)):
    """Indicateurs RH consolidés (démographie, mouvements, absences, alertes)."""
    company_id = resolve_company_id_for_user(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )
    try:
        result = queries.get_company_overview(company_id, current_user)
        return CompanyOverviewResponse(
            demographics=result.demographics,
            movements=result.movements,
            absenteeism=result.absenteeism,
            alerts=result.alerts,
            compliance=result.compliance,
            cdd_ending_within_30_days=result.cdd_ending_within_30_days,
            dsn_coverage=result.dsn_coverage,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/details", response_model=CompanyDetailsResponse)
def patch_company_details(
    body: CompanyDetailsUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour les informations administratives de l'entreprise active."""
    company_id = resolve_company_id_for_user(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Droits insuffisants pour modifier l'entreprise",
        )
    try:
        commands.update_company_details(
            company_id, body.to_update_dict(), current_user
        )
        result = queries.get_company_details_and_kpis(company_id, current_user)
        return CompanyDetailsResponse(
            company_data=result.company_data,
            kpis=result.kpis,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/export")
def export_company_dashboard(
    format: str = Query("csv", pattern="^(csv)$"),
    current_user: User = Depends(get_current_user),
):
    """Export CSV du tableau de bord Mon Entreprise."""
    company_id = resolve_company_id_for_user(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise",
        )
    try:
        details = queries.get_company_details_and_kpis(company_id, current_user)
        overview = queries.get_company_overview(company_id, current_user)
        csv_content = build_company_export_csv(
            details.company_data,
            details.kpis,
            overview.demographics,
            overview.movements,
        )
        name = (details.company_data.get("company_name") or "entreprise").replace(
            " ", "_"
        )
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="mon_entreprise_{name}.csv"'
            },
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
