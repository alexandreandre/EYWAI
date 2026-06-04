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
    _to_http,
)
from app.modules.collective_agreements.domain.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


def create_catalog_item(
    data: CatalogCreateInput,
    is_platform_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> dict[str, Any]:
    """Crée une entrée catalogue (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.create_catalog_item(data, is_platform_admin)


def update_catalog_item(
    agreement_id: str,
    update_dict_raw: dict[str, Any],
    is_platform_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> Optional[dict[str, Any]]:
    """Met à jour une entrée catalogue (super admin). update_dict_raw = model_dump(exclude_unset=True)."""
    svc = service or get_collective_agreements_service()
    return svc.update_catalog_item(agreement_id, update_dict_raw, is_platform_admin)


def delete_catalog_item(
    agreement_id: str,
    is_platform_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> bool:
    """Supprime une entrée catalogue (super admin)."""
    svc = service or get_collective_agreements_service()
    return svc.delete_catalog_item(agreement_id, is_platform_admin)


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
    is_platform_admin: bool,
    service: Optional[CollectiveAgreementsService] = None,
) -> None:
    """Force le rafraîchissement du cache texte PDF (super admin)."""
    svc = service or get_collective_agreements_service()
    svc.refresh_text_cache(agreement_id, is_platform_admin)


def extract_rules(
    agreement_id: str,
    is_platform_admin: bool,
    *,
    dry_run: bool = False,
) -> dict:
    """Extrait et persiste les règles paie pour une convention (super admin)."""
    if not is_platform_admin:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Accès réservé au super administrateur"
        )
    from app.modules.collective_agreements.rules.service import get_cc_rules_service

    try:
        outcome = get_cc_rules_service().extract_and_persist_by_agreement_id(
            agreement_id, dry_run=dry_run
        )
    except (NotFoundError, ForbiddenError, ValidationError) as exc:
        raise _to_http(exc)
    return {
        "success": outcome.success,
        "idcc": outcome.idcc,
        "agreement_id": outcome.agreement_id,
        "rules": outcome.rules,
        "error": outcome.error,
        "tokens_used": outcome.tokens_used,
        "confidence": outcome.confidence,
        "log_id": outcome.log_id,
    }


def extract_rules_batch(
    is_platform_admin: bool,
    *,
    idcc_list: Optional[list[str]] = None,
    all_catalog: bool = False,
    priority_only: bool = False,
    dry_run: bool = False,
) -> dict:
    """Extraction batch des règles paie (super admin)."""
    if not is_platform_admin:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Accès réservé au super administrateur"
        )
    from app.modules.collective_agreements.rules.service import get_cc_rules_service

    outcomes = get_cc_rules_service().extract_batch(
        idcc_list=idcc_list,
        all_catalog=all_catalog,
        priority_only=priority_only,
        dry_run=dry_run,
    )
    results = [
        {
            "success": o.success,
            "idcc": o.idcc,
            "agreement_id": o.agreement_id,
            "rules": o.rules,
            "error": o.error,
            "tokens_used": o.tokens_used,
            "confidence": o.confidence,
            "log_id": o.log_id,
        }
        for o in outcomes
    ]
    succeeded = sum(1 for r in results if r["success"])
    return {
        "results": results,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
    }


def _kali_outcome_to_dict(outcome) -> dict:
    rules = None
    if outcome.rules_extraction:
        rules = {
            "success": outcome.rules_extraction.success,
            "error": outcome.rules_extraction.error,
            "confidence": outcome.rules_extraction.confidence,
        }
    return {
        "success": outcome.success,
        "idcc": outcome.idcc,
        "agreement_id": outcome.agreement_id,
        "title": outcome.title,
        "legifrance_url": outcome.legifrance_url,
        "character_count": outcome.character_count,
        "created": outcome.created,
        "error": outcome.error,
        "rules": rules,
    }


def import_from_legifrance(
    idcc: str,
    is_platform_admin: bool,
    *,
    extract_rules: bool = True,
    sector: Optional[str] = None,
) -> dict:
    """Importe une CC depuis Légifrance KALI (super admin)."""
    if not is_platform_admin:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Accès réservé au super administrateur"
        )
    from app.modules.collective_agreements.application.kali_import import (
        get_kali_import_service,
    )

    outcome = get_kali_import_service().import_by_idcc(
        idcc, extract_rules=extract_rules, sector=sector
    )
    return _kali_outcome_to_dict(outcome)


def import_from_legifrance_batch(
    is_platform_admin: bool,
    *,
    idcc_list: Optional[list[str]] = None,
    priority_only: bool = False,
    extract_rules: bool = True,
) -> dict:
    """Import batch depuis Légifrance KALI (super admin)."""
    if not is_platform_admin:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Accès réservé au super administrateur"
        )
    from app.modules.collective_agreements.application.kali_import import (
        get_kali_import_service,
    )

    outcomes = get_kali_import_service().import_batch(
        idcc_list=idcc_list,
        priority_only=priority_only,
        extract_rules=extract_rules,
    )
    results = [_kali_outcome_to_dict(o) for o in outcomes]
    succeeded = sum(1 for r in results if r["success"])
    return {
        "results": results,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
    }


def rollback_rules(
    log_id: str,
    is_platform_admin: bool,
) -> dict:
    """Restaure les règles paie depuis le journal d'extraction (super admin)."""
    if not is_platform_admin:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail="Accès réservé au super administrateur"
        )
    from app.modules.collective_agreements.rules.service import get_cc_rules_service

    row = get_cc_rules_service().rollback(log_id)
    if not row:
        return {
            "success": False,
            "rules": None,
            "message": "Rollback impossible (log introuvable ou sans version précédente)",
        }
    return {"success": True, "rules": row.get("rules"), "message": "Rollback effectué"}
