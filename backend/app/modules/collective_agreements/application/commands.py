"""
Commandes applicatives (write) pour collective_agreements.

Délèguent au CollectiveAgreementsService (logique extraite des routers legacy).
"""
from __future__ import annotations

from typing import Any, Optional

from app.modules.collective_agreements.application.dto import CatalogCreateInput
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)


def create_catalog_item(
    data: CatalogCreateInput,
    is_super_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> dict[str, Any]:
    """Crée une entrée catalogue (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.create_catalog_item(data, is_super_admin)


def update_catalog_item(
    agreement_id: str,
    update_dict_raw: dict[str, Any],
    is_super_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> Optional[dict[str, Any]]:
    """Met à jour une entrée catalogue (super admin). update_dict_raw = model_dump(exclude_unset=True)."""
    svc = service or get_collective_agreements_service()
    return svc.update_catalog_item(agreement_id, update_dict_raw, is_super_admin)


def delete_catalog_item(
    agreement_id: str,
    is_super_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> bool:
    """Supprime une entrée catalogue (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.delete_catalog_item(agreement_id, is_super_admin)


def assign_agreement_to_company(
    company_id: str,
    collective_agreement_id: str,
    user_id: str,
    has_rh_access: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> dict:
    """Assigne une convention à l'entreprise (RH)."""
    svc = service or get_collective_agreements_service()
    return svc.assign_to_company(
        company_id, collective_agreement_id, user_id, has_rh_access
    )


def unassign_agreement_from_company(
    assignment_id: str,
    company_id: str,
    has_rh_access: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> bool:
    """Retire une assignation (RH)."""
    svc = service or get_collective_agreements_service()
    return svc.unassign_from_company(assignment_id, company_id, has_rh_access)


def refresh_text_cache(
    agreement_id: str,
    is_super_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> None:
    """Force le rafraîchissement du cache texte PDF (super admin)."""
    svc = service or get_collective_agreements_service()
    svc.refresh_text_cache(agreement_id, is_super_admin)
