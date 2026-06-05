"""
Requêtes applicatives (read) pour collective_agreements.

Délèguent au CollectiveAgreementsService (logique extraite des routers legacy).
"""

from __future__ import annotations

from typing import Any, List, Optional

from app.modules.collective_agreements.application.dto import (
    QuestionOutput,
    UploadUrlOutput,
)
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
    _to_http,
)
from app.modules.collective_agreements.domain.exceptions import ForbiddenError, NotFoundError


def list_catalog_query(
    sector: Optional[str] = None,
    search: Optional[str] = None,
    active_only: bool = True,
    service: Optional[CollectiveAgreementsService] = None,
) -> List[dict]:
    """Liste le catalogue (tous utilisateurs authentifiés)."""
    svc = service or get_collective_agreements_service()
    return svc.list_catalog(sector=sector, search=search, active_only=active_only)


def get_catalog_item_query(
    agreement_id: str,
    service: Optional[CollectiveAgreementsService] = None,
) -> Optional[dict]:
    """Récupère une entrée catalogue par id."""
    svc = service or get_collective_agreements_service()
    return svc.get_catalog_item(agreement_id)


def get_classifications_query(
    agreement_id: str,
    service: Optional[CollectiveAgreementsService] = None,
) -> List[Any]:
    """Grille de classification conventionnelle pour une convention (idcc)."""
    svc = service or get_collective_agreements_service()
    return svc.get_classifications(agreement_id)


def get_upload_url_query(
    filename: str,
    service: Optional[CollectiveAgreementsService] = None,
) -> UploadUrlOutput:
    """URL signée pour upload PDF (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.get_upload_url(filename)


def get_my_company_agreements_query(
    company_id: str,
    has_rh_access: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> List[dict]:
    """Liste les conventions assignées à l'entreprise (RH)."""
    svc = service or get_collective_agreements_service()
    return svc.get_my_company_agreements(company_id, has_rh_access)


def get_all_assignments_query(
    is_platform_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> List[dict]:
    """Toutes les assignations par entreprise (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.get_all_assignments(is_platform_admin)


def ask_question_query(
    agreement_id: str,
    question: str,
    company_id: str,
    has_rh_access: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> QuestionOutput:
    """Chat : pose une question sur une convention."""
    svc = service or get_collective_agreements_service()
    return svc.ask_question(agreement_id, question, company_id, has_rh_access)


def get_convention_document_query(
    agreement_id: str,
    doc_kind: str,
    *,
    company_id: Optional[str],
    has_rh_access: bool,
    is_platform_admin: bool,
) -> tuple[bytes, str]:
    """Génère le PDF (texte intégral ou synthèse) d'une convention pour les RH."""
    from app.modules.collective_agreements.application.documents import (
        get_cc_document_service,
    )

    try:
        return get_cc_document_service().get_document(
            agreement_id,
            doc_kind,
            company_id=company_id,
            has_rh_access=has_rh_access,
            is_platform_admin=is_platform_admin,
        )
    except (NotFoundError, ForbiddenError) as exc:
        raise _to_http(exc)
    except ValidationError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=exc.message)


def get_rules_status_query(
    agreement_id: str,
    is_platform_admin: bool,
    company_id: Optional[str] = None,
    has_rh_access: bool = False,
) -> dict:
    """Statut des règles paie extraites pour une convention."""
    if not is_platform_admin:
        if not has_rh_access or not company_id:
            raise _to_http(ForbiddenError("Accès non autorisé"))
        from app.modules.collective_agreements.infrastructure.repository import (
            CollectiveAgreementRepository,
        )

        if not CollectiveAgreementRepository().check_assignment_exists(
            company_id, agreement_id
        ):
            raise _to_http(
                ForbiddenError("Cette convention n'est pas assignée à votre entreprise")
            )

    from app.modules.collective_agreements.application.kali_import import (
        get_kali_import_service,
    )
    from app.modules.collective_agreements.rules.service import get_cc_rules_service

    try:
        status = get_cc_rules_service().get_rules_status(agreement_id)
    except NotFoundError as exc:
        raise _to_http(exc)
    text_source = get_kali_import_service().get_text_source(agreement_id)
    return {
        "idcc": status.idcc,
        "agreement_id": status.agreement_id,
        "has_rules": status.has_rules,
        "rules": status.rules,
        "source_text_hash": status.source_text_hash,
        "extracted_at": status.extracted_at,
        "extraction_model": status.extraction_model,
        "latest_log_status": status.latest_log_status,
        "latest_log_error": status.latest_log_error,
        "confidence": status.confidence,
        "text_source": text_source,
    }
