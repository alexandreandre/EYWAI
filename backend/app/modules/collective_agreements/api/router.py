"""
Router API collective_agreements : catalogue, assignations, chat.

Appelle uniquement l'application du module (commands / queries).
Aucune logique métier : validation des entrées (schémas), injection du contexte user, appel application, retour du résultat.
Comportement HTTP identique au legacy (api/routers/collective_agreements*.py).
"""

from __future__ import annotations

import traceback
from io import BytesIO
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

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
    CollectiveAgreementSuggestResponse,
    CompanyCollectiveAgreementWithDetails,
    KaliImportBatchRequest,
    KaliImportBatchResponse,
    KaliImportCancelRequest,
    KaliImportCancelResponse,
    KaliImportRequest,
    KaliImportResponse,
    KaliSyncCatalogRequest,
    ExtractRulesBatchRequest,
    ExtractRulesBatchResponse,
    ExtractRulesResponse,
    ExtractTrainingsResponse,
    GetUploadUrlBody,
    QuestionRequest,
    QuestionResponse,
    RollbackRulesResponse,
    RulesStatusResponse,
    CcTrainingRecommendation,
    CcTrainingRecommendationUpdate,
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
def list_catalog(
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


@router.get("/catalog/suggest", response_model=CollectiveAgreementSuggestResponse)
def suggest_catalog(
    q: str = Query(..., min_length=2, description="Recherche en langage naturel ou IDCC"),
    limit: int = Query(10, ge=1, le=20),
    active_only: bool = Query(True),
    include_kali: bool = Query(
        True, description="Compléter avec Légifrance si peu de résultats catalogue"
    ),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Propose des conventions (IDCC + intitulé) à partir d'une recherche textuelle."""
    try:
        suggestions = queries.suggest_catalog_query(
            q,
            limit=limit,
            active_only=active_only,
            include_kali=include_kali,
        )
        return {"suggestions": suggestions}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{agreement_id}", response_model=CollectiveAgreementCatalog)
def get_catalog_item(
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
def get_agreement_classifications(
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


@router.get("/catalog/{agreement_id}/salary-minima")
def get_agreement_salary_minima(
    agreement_id: str,
    code_postal: str | None = Query(None, description="Code postal établissement"),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Grille des minima salariaux CC (coefficient → € mensuel)."""
    try:
        return queries.get_salary_minima_query(agreement_id, code_postal=code_postal)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Gestion catalogue (super admin) ---


@router.post("/catalog/upload-url")
def get_catalog_upload_url(
    body: GetUploadUrlBody,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Génère une URL signée pour uploader un PDF (super admin)."""
    try:
        if not current_user.is_platform_admin:
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
def create_catalog_item(
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
            data, is_platform_admin=current_user.is_platform_admin
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/catalog/{agreement_id}", response_model=CollectiveAgreementCatalog)
def update_catalog_item(
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
            is_platform_admin=current_user.is_platform_admin,
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
def delete_catalog_item(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Supprime une convention du catalogue (super admin)."""
    try:
        commands.delete_catalog_item(
            agreement_id, is_platform_admin=current_user.is_platform_admin
        )
        return None
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Assignations (RH) ---


@router.get("/my-company", response_model=List[CompanyCollectiveAgreementWithDetails])
def get_my_company_agreements(
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
def assign_agreement_to_company(
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
def unassign_agreement_from_company(
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


# --- Documents PDF (texte intégral + synthèse) ---


def _stream_convention_document(
    agreement_id: str,
    doc_kind: str,
    current_user: CollectiveAgreementUserContext,
) -> StreamingResponse:
    company_id = current_user.active_company_id
    has_rh_access = bool(
        company_id and current_user.has_rh_access_in_company(str(company_id))
    )
    pdf_bytes, filename = queries.get_convention_document_query(
        agreement_id,
        doc_kind,
        company_id=str(company_id) if company_id else None,
        has_rh_access=has_rh_access,
        is_platform_admin=current_user.is_platform_admin,
    )
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/catalog/{agreement_id}/document/full-text")
def get_convention_full_text_pdf(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """PDF du texte intégral de la convention (RH de l'entreprise assignée)."""
    try:
        return _stream_convention_document(agreement_id, "full-text", current_user)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{agreement_id}/document/synthesis")
def get_convention_synthesis_pdf(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """PDF de synthèse pédagogique (IA) de la convention (RH de l'entreprise assignée)."""
    try:
        return _stream_convention_document(agreement_id, "synthesis", current_user)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Super admin : vue globale ---


@router.get("/all-assignments")
def get_all_company_assignments(
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Toutes les assignations par entreprise (super admin)."""
    try:
        if not current_user.is_platform_admin:
            raise HTTPException(
                status_code=403, detail="Accès réservé au super administrateur"
            )
        return queries.get_all_assignments_query(is_platform_admin=True)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Import Légifrance KALI (super admin) ---


@router.post(
    "/catalog/import-legifrance",
    response_model=KaliImportResponse,
)
def import_from_legifrance(
    body: KaliImportRequest,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Importe une CC depuis Légifrance (KALI) + extraction règles paie optionnelle."""
    try:
        return commands.import_from_legifrance(
            body.idcc,
            is_platform_admin=current_user.is_platform_admin,
            extract_rules=body.extract_rules,
            sector=body.sector,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/import-legifrance/batch",
    response_model=KaliImportBatchResponse,
)
def import_from_legifrance_batch(
    body: KaliImportBatchRequest,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Import batch depuis Légifrance (lot prioritaire ou liste IDCC)."""
    try:
        return commands.import_from_legifrance_batch(
            is_platform_admin=current_user.is_platform_admin,
            idcc_list=body.idcc_list,
            priority_only=body.priority_only,
            extract_rules=body.extract_rules,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/sync-legifrance",
    response_model=KaliImportBatchResponse,
)
def sync_catalog_from_legifrance(
    body: KaliSyncCatalogRequest = Body(default_factory=KaliSyncCatalogRequest),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Synchronise toutes les CC actives du catalogue depuis Légifrance (super admin)."""
    try:
        return commands.sync_catalog_from_legifrance(
            is_platform_admin=current_user.is_platform_admin,
            extract_rules=body.extract_rules,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/kali-import/cancel",
    response_model=KaliImportCancelResponse,
)
def cancel_kali_import(
    body: KaliImportCancelRequest,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Interrompt un import ou une sync Légifrance en cours (super admin)."""
    try:
        return commands.cancel_kali_import(
            is_platform_admin=current_user.is_platform_admin,
            idcc=body.idcc,
            catalog_sync=body.catalog_sync,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/{agreement_id}/import-legifrance",
    response_model=KaliImportResponse,
)
def import_agreement_from_legifrance(
    agreement_id: str,
    extract_rules: bool = Query(True),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Ré-importe depuis Légifrance pour une fiche catalogue existante (par IDCC)."""
    try:
        item = queries.get_catalog_item_query(agreement_id)
        if not item:
            raise HTTPException(status_code=404, detail="Convention non trouvée")
        return commands.import_from_legifrance(
            item["idcc"],
            is_platform_admin=current_user.is_platform_admin,
            extract_rules=extract_rules,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Règles paie — extraction IA (super admin) ---


@router.post(
    "/catalog/{agreement_id}/extract-rules",
    response_model=ExtractRulesResponse,
)
def extract_rules(
    agreement_id: str,
    dry_run: bool = Query(False, description="Simuler sans appel IA"),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Extrait les règles paie depuis le texte CC et les persiste (super admin)."""
    try:
        return commands.extract_rules(
            agreement_id,
            is_platform_admin=current_user.is_platform_admin,
            dry_run=dry_run,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/extract-rules/batch",
    response_model=ExtractRulesBatchResponse,
)
def extract_rules_batch(
    body: ExtractRulesBatchRequest,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Extraction batch des règles paie (super admin)."""
    try:
        return commands.extract_rules_batch(
            is_platform_admin=current_user.is_platform_admin,
            idcc_list=body.idcc_list,
            all_catalog=body.all_catalog,
            priority_only=body.priority_only,
            dry_run=body.dry_run,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- Formations CC — extraction IA (super admin) ---


@router.post(
    "/catalog/{agreement_id}/extract-trainings",
    response_model=ExtractTrainingsResponse,
)
def extract_trainings(
    agreement_id: str,
    dry_run: bool = Query(False, description="Simuler sans appel IA"),
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Extrait les propositions formation depuis le texte CC (super admin)."""
    try:
        return commands.extract_trainings(
            agreement_id,
            is_platform_admin=current_user.is_platform_admin,
            dry_run=dry_run,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/catalog/{agreement_id}/training-recommendations",
    response_model=List[CcTrainingRecommendation],
)
def list_training_recommendations(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Liste les propositions formation CC pour une convention (super admin)."""
    try:
        return commands.list_training_recommendations(
            agreement_id,
            is_platform_admin=current_user.is_platform_admin,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/training-recommendations/{recommendation_id}",
    response_model=CcTrainingRecommendation,
)
def patch_training_recommendation(
    recommendation_id: str,
    body: CcTrainingRecommendationUpdate,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Active/désactive ou édite une proposition formation CC (super admin)."""
    try:
        return commands.update_training_recommendation(
            recommendation_id,
            is_platform_admin=current_user.is_platform_admin,
            patch=body.model_dump(exclude_unset=True),
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/catalog/{agreement_id}/rules-status",
    response_model=RulesStatusResponse,
)
def get_rules_status(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Statut des règles paie extraites (super admin ou RH avec convention assignée)."""
    try:
        company_id = current_user.active_company_id
        has_rh_access = bool(
            company_id and current_user.has_rh_access_in_company(str(company_id))
        )
        return queries.get_rules_status_query(
            agreement_id,
            is_platform_admin=current_user.is_platform_admin,
            company_id=str(company_id) if company_id else None,
            has_rh_access=has_rh_access,
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/catalog/rules/rollback/{log_id}",
    response_model=RollbackRulesResponse,
)
def rollback_rules(
    log_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Restaure les règles paie depuis le journal d'extraction (super admin)."""
    try:
        return commands.rollback_rules(
            log_id, is_platform_admin=current_user.is_platform_admin
        )
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
def ask_question(
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
def refresh_cache(
    agreement_id: str,
    current_user: CollectiveAgreementUserContext = Depends(get_current_user),
):
    """Force le rafraîchissement du cache texte (super admin)."""
    try:
        if not current_user.is_platform_admin:
            raise HTTPException(
                status_code=403, detail="Accès réservé au super administrateur"
            )
        commands.refresh_text_cache(agreement_id, is_platform_admin=True)
        return {"message": "Cache rafraîchi avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
