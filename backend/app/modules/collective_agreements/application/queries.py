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
)


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
    is_super_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> List[dict]:
    """Toutes les assignations par entreprise (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.get_all_assignments(is_super_admin)


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
