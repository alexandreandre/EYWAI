"""
Router API collective_agreements : catalogue, assignations, chat.

Appelle uniquement l'application du module (commands / queries).
Aucune logique métier : validation des entrées (schémas), injection du contexte user, appel application, retour du résultat.
Comportement HTTP identique au legacy (api/routers/collective_agreements*.py).
"""

from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.modules.collective_agreements.api.dependencies import (
    CollectiveAgreementUserContext,
    get_current_user,
)
from app.modules.collective_agreements.application import commands, queries
from app.modules.collective_agreements.application.dto import CatalogCreateInput
from app.modules.collective_agreements.schemas import (
    CollectiveAgreementCatalog,
    CollectiveAgreementCatalogCreate,
    CollectiveAgreementCatalogUpdate,
    CompanyCollectiveAgreementWithDetails,
    GetUploadUrlBody,
    QuestionRequest,
    QuestionResponse,
)

# --- Router principal (catalogue + assignations) ---

router = APIRouter(
    prefix="/api/collective-agreements",
    tags=["Collective Agreements"],
)


def _ensure_company_id(user: CollectiveAgreementUserContext) -> str:
    """Contexte entreprise requis pour les routes RH/assignations."""
    if not user.active_company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(user.active_company_id)


# --- Catalogue (lecture pour tous) ---


@router.get("/catalog", response_model=List[CollectiveAgreementCatalog])
async def list_catalog(
    sector: str | None = Query(None, description="Filtrer par secteur"),
    search: str | None = Query(None, description="Rechercher par nom ou IDCC"),
    active_only: bool = Query(
        True, description="Afficher uniquement les conventions actives"
    ),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Liste toutes les conventions du catalogue (dropdown)."""
    try:
        return queries.list_catalog_query(
            sector=sector, search=search, active_only=active_only
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{agreement_id}", response_model=CollectiveAgreementCatalog)
async def get_catalog_item(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Récupère une convention du catalogue par son ID."""
    try:
        item = queries.get_catalog_item_query(agreement_id)
        if not item:
            raise HTTPException(
                status_code=404, detail="Convention collective non trouvée"
            )
        return item
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{agreement_id}/classifications")
async def get_agreement_classifications(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Grille de classification conventionnelle pour une convention."""
    try:
        return queries.get_classifications_query(agreement_id)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Gestion catalogue (super admin) ---


@router.post("/catalog/upload-url")
async def get_catalog_upload_url(
    body: GetUploadUrlBody,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un PDF (super admin)."""
    try:
        if current_user.role != "super_admin":
            raise HTTPException(
                status_code=403, detail="Accès réservé au super administrateur"
            )
        out = queries.get_upload_url_query(body.filename)
        return {"path": out.path, "signedURL": out.signed_url}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalog", response_model=CollectiveAgreementCatalog, status_code=201)
async def create_catalog_item(
    agreement_data: CollectiveAgreementCatalogCreate,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Crée une nouvelle convention dans le catalogue (super admin)."""
    try:
        data = CatalogCreateInput(
            name=agreement_data.name,
            idcc=agreement_data.idcc,
            description=agreement_data.description,
            sector=agreement_data.sector,
            effective_date=agreement_data.effective_date,
            is_active=agreement_data.is_active,
            rules_pdf_path=agreement_data.rules_pdf_path,
            rules_pdf_filename=agreement_data.rules_pdf_filename,
        )
        return commands.create_catalog_item(
            data, is_super_admin=(current_user.role == "super_admin")
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/catalog/{agreement_id}", response_model=CollectiveAgreementCatalog)
async def update_catalog_item(
    agreement_id: str,
    update_data: CollectiveAgreementCatalogUpdate,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Met à jour une convention du catalogue (super admin)."""
    try:
        update_dict_raw = update_data.model_dump(exclude_unset=True)
        out = commands.update_catalog_item(
            agreement_id,
            update_dict_raw,
            is_super_admin=(current_user.role == "super_admin"),
        )
        if not out:
            raise HTTPException(
                status_code=404, detail="Convention collective non trouvée"
            )
        return out
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/catalog/{agreement_id}", status_code=204)
async def delete_catalog_item(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Supprime une convention du catalogue (super admin)."""
    try:
        commands.delete_catalog_item(
            agreement_id, is_super_admin=(current_user.role == "super_admin")
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Assignations (RH) ---


@router.get("/my-company", response_model=List[CompanyCollectiveAgreementWithDetails])
async def get_my_company_agreements(
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Récupère les conventions assignées à l'entreprise de l'utilisateur."""
    try:
        company_id = _ensure_company_id(current_user)
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        return queries.get_my_company_agreements_query(
            company_id, current_user.has_rh_access_in_company(company_id)
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assign", status_code=201)
async def assign_agreement_to_company(
    collective_agreement_id: str = Body(..., embed=True),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Assigne une convention à l'entreprise de l'utilisateur."""
    try:
        company_id = _ensure_company_id(current_user)
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        result = commands.assign_agreement_to_company(
            company_id,
            collective_agreement_id,
            str(current_user.id),
            current_user.has_rh_access_in_company(company_id),
        )
        return {
            "message": "Convention collective assignée avec succès",
            "assignment": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unassign/{assignment_id}", status_code=204)
async def unassign_agreement_from_company(
    assignment_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Retire une convention de l'entreprise de l'utilisateur."""
    try:
        company_id = _ensure_company_id(current_user)
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        commands.unassign_agreement_from_company(
            assignment_id, company_id, current_user.has_rh_access_in_company(company_id)
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Super admin : vue globale ---


@router.get("/all-assignments")
async def get_all_company_assignments(
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Toutes les assignations par entreprise (super admin)."""
    try:
        if current_user.role != "super_admin":
            raise HTTPException(
                status_code=403, detail="Accès réservé au super administrateur"
            )
        return queries.get_all_assignments_query(is_super_admin=True)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Router Chat (conventions collectives) ---

router_chat = APIRouter(
    prefix="/api/collective-agreements-chat",
    tags=["Collective Agreements Chat"],
)


@router_chat.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Pose une question sur une convention collective (LLM + cache PDF)."""
    try:
        company_id = _ensure_company_id(current_user)
        if not current_user.has_rh_access_in_company(company_id):
            raise HTTPException(status_code=403, detail="Accès non autorisé")
        out = queries.ask_question_query(
            request.agreement_id,
            request.question,
            company_id,
            current_user.has_rh_access_in_company(company_id),
        )
        return QuestionResponse(answer=out.answer, agreement_name=out.agreement_name)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router_chat.post("/refresh-cache/{agreement_id}")
async def refresh_cache(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Force le rafraîchissement du cache texte (super admin)."""
    try:
        if current_user.role != "super_admin":
            raise HTTPException(
                status_code=403, detail="Accès réservé au super administrateur"
            )
        commands.refresh_text_cache(agreement_id, is_super_admin=True)
        return {"message": "Cache rafraîchi avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
