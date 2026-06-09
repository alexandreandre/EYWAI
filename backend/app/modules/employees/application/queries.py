"""
Cas d'usage en lecture du module employees.

Délègue au repository, storage provider et queries infrastructure.
Comportement identique au router legacy. Aucun accès DB direct.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.employees.application.service import (
    enrich_employee_with_annual_review,
    enrich_employee_with_exit_context,
    enrich_employee_with_residence_permit_status,
    enrich_employee_with_trial_period_status,
)
from app.modules.employees.infrastructure.providers import (
    get_employee_rh_access as provider_get_employee_rh_access,
    get_promotions as provider_get_promotions,
    get_storage_provider,
)
from app.modules.employees.infrastructure.queries import (
    fetch_published_exit_documents,
    get_company_id_for_user_from_profile,
    get_employee_company_id,
    resolve_employee_id_for_user_account,
)
from app.core.database import supabase
from app.modules.employees.infrastructure.repository import EmployeeRepository
from app.modules.onboarding.domain.profile import enrich_employee_profile_completeness

# Repository partagé (pas d'injection pour l'instant, comportement identique)
_employee_repository = EmployeeRepository()


def _storage_signed_urls(
    bucket: str, path: str, *, expiry_seconds: int = 3600
) -> tuple[Optional[str], Optional[str]]:
    storage = get_storage_provider()
    return (
        storage.create_signed_url(
            bucket, path, expiry_seconds=expiry_seconds, download=True
        ),
        storage.create_signed_url(
            bucket, path, expiry_seconds=expiry_seconds, download=False
        ),
    )


def get_contract_urls(employee_id: str) -> tuple[Optional[str], Optional[str]]:
    """URLs signées (téléchargement, aperçu) du contrat PDF."""
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None, None
    storage = get_storage_provider()
    list_response = storage.list_files("contracts", f"{company_id}/{employee_id}")
    if not any(f.get("name") == "contrat.pdf" for f in list_response):
        return None, None
    return _storage_signed_urls(
        "contracts", f"{company_id}/{employee_id}/contrat.pdf"
    )


def get_identity_document_urls(employee_id: str) -> tuple[Optional[str], Optional[str]]:
    """URLs signées (téléchargement, aperçu) de la pièce d'identité."""
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None, None
    storage = get_storage_provider()
    list_response = storage.list_files("piece_identite", f"{company_id}/{employee_id}")
    for ext in [".pdf", ".jpg", ".jpeg", ".png"]:
        name = f"piece_identite{ext}"
        if any(f.get("name") == name for f in list_response):
            return _storage_signed_urls(
                "piece_identite", f"{company_id}/{employee_id}/{name}"
            )
    return None, None


def get_credentials_pdf_urls(employee_id: str) -> tuple[Optional[str], Optional[str]]:
    """URLs signées (téléchargement, aperçu) du PDF identifiants."""
    from app.modules.employees.application.credentials_pdf import (
        ensure_credentials_pdf,
    )

    path = ensure_credentials_pdf(employee_id)
    if not path:
        return None, None
    from app.modules.employees.application.credentials_pdf import CREDENTIALS_BUCKET

    return _storage_signed_urls(CREDENTIALS_BUCKET, path)


def employee_has_work_contract(employee_id: str, company_id: str) -> bool:
    """
    True si un contrat de travail existe pour le salarié :
    fichier signé (contrat.pdf) ou document généré (catégorie contrat).
    """
    storage = get_storage_provider()
    list_response = storage.list_files("contracts", f"{company_id}/{employee_id}")
    if any(f.get("name") == "contrat.pdf" for f in list_response):
        return True
    response = (
        supabase.table("generated_documents")
        .select("id")
        .eq("company_id", company_id)
        .eq("employee_id", employee_id)
        .eq("category", "contrat")
        .limit(1)
        .execute()
    )
    return bool(response.data)


def get_employees(company_id: str) -> List[Dict[str, Any]]:
    """
    Liste des employés de l'entreprise (enrichis titre de séjour).
    Comportement identique à get_employees (router legacy).
    """
    rows = _employee_repository.get_by_company(company_id)
    return [
        enrich_employee_with_trial_period_status(
            enrich_employee_with_residence_permit_status(row)
        )
        for row in rows
    ]


def get_employees_summary(
    company_id: str,
    *,
    active_only: bool = False,
    payroll_ready_only: bool = False,
) -> List[Dict[str, Any]]:
    """Liste légère sans enrichissement (grilles RH, planning)."""
    return _employee_repository.get_summary_by_company(
        company_id,
        active_only=active_only,
        payroll_ready_only=payroll_ready_only,
    )


def get_employee_by_id(employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """
    Détail d'un employé (enrichi titre de séjour + entretien annuel).
    Comportement identique à get_employee_details (router legacy).
    """
    data = _employee_repository.get_by_id(employee_id, company_id)
    if not data:
        return None
    data = enrich_employee_with_residence_permit_status(data)
    data = enrich_employee_with_trial_period_status(data)
    data = enrich_employee_with_annual_review(data)
    data = enrich_employee_with_exit_context(data)
    return enrich_employee_profile_completeness(data)


def get_my_employee_profile(user_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """
    Fiche collaborateur de l'utilisateur connecté (résolution user_id → employees.id).
    """
    employee_id = resolve_employee_id_for_user_account(user_id, company_id)
    if not employee_id:
        return None
    return get_employee_by_id(employee_id, company_id)


def get_my_contract_url(employee_id: str) -> Optional[str]:
    """
    URL signée de téléchargement du contrat (espace employé).
    Comportement identique à get_my_contract (router legacy).
    """
    download_url, _ = get_contract_urls(employee_id)
    return download_url


def get_my_contract_preview_url(employee_id: str) -> Optional[str]:
    """URL signée d'aperçu inline du contrat."""
    _, preview_url = get_contract_urls(employee_id)
    return preview_url


def get_my_published_exit_documents(
    employee_id: str,
) -> List[Dict[str, Any]]:
    """
    Liste des documents de sortie publiés pour l'employé (espace employé).
    Comportement identique à get_my_published_exit_documents (router legacy).
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return []
    return fetch_published_exit_documents(employee_id, company_id)


def get_credentials_pdf_url(employee_id: str) -> Optional[str]:
    """
    URL signée du PDF de création de compte (espace RH).
    Génère le PDF s'il est absent (nouveau mot de passe temporaire).
    """
    download_url, _ = get_credentials_pdf_urls(employee_id)
    return download_url


def get_credentials_pdf_preview_url(employee_id: str) -> Optional[str]:
    """URL signée d'aperçu inline du PDF identifiants."""
    _, preview_url = get_credentials_pdf_urls(employee_id)
    return preview_url


def get_identity_document_url(employee_id: str) -> Optional[str]:
    """
    URL signée de la pièce d'identité (espace RH).
    Comportement identique à get_employee_identity_document_url (router legacy).
    """
    download_url, _ = get_identity_document_urls(employee_id)
    return download_url


def get_identity_document_preview_url(employee_id: str) -> Optional[str]:
    """URL signée d'aperçu inline de la pièce d'identité."""
    _, preview_url = get_identity_document_urls(employee_id)
    return preview_url


def get_contract_url(employee_id: str) -> Optional[str]:
    """
    URL signée du contrat PDF (espace RH).
    Comportement identique à get_employee_contract_url (router legacy).
    """
    download_url, _ = get_contract_urls(employee_id)
    return download_url


def get_contract_preview_url(employee_id: str) -> Optional[str]:
    """URL signée d'aperçu inline du contrat PDF."""
    _, preview_url = get_contract_urls(employee_id)
    return preview_url


def get_employee_promotions(company_id: str, employee_id: str) -> List[Dict[str, Any]]:
    """
    Liste des promotions d'un employé. Délègue au service promotions.
    Comportement identique à get_employee_promotions (router legacy).
    """
    return provider_get_promotions(company_id=company_id, employee_id=employee_id)


def get_company_id_for_creator(user_id: str) -> Optional[str]:
    """Company_id de l'utilisateur connecté (depuis profil) pour la création d'employé."""
    return get_company_id_for_user_from_profile(user_id)


def get_employee_rh_access(employee_id: str, company_id: str) -> Dict[str, Any]:
    """
    Accès RH actuel et rôles disponibles pour un employé.
    Comportement identique à get_employee_rh_access_info (router legacy).
    """
    return provider_get_employee_rh_access(
        employee_id=employee_id, company_id=company_id
    )


def employee_belongs_to_company(employee_id: str, company_id: str) -> bool:
    """Indique si l'employé appartient bien à l'entreprise (ex. contrôle d'accès onboarding)."""
    cid = get_employee_company_id(employee_id)
    return cid is not None and str(cid) == str(company_id)


def get_employees_filtered(
    company_id: str,
    service_id: str | None = None,
    statut: str | None = None,
    contract_type: str | None = None,
    anciennete_min_mois: int | None = None,
    salaire_min: float | None = None,
    salaire_max: float | None = None,
) -> List[Dict[str, Any]]:
    """Employés actifs filtrés (simulation / augmentation collective)."""
    return _employee_repository.get_employees_filtered(
        company_id,
        service_id=service_id,
        statut=statut,
        contract_type=contract_type,
        anciennete_min_mois=anciennete_min_mois,
        salaire_min=salaire_min,
        salaire_max=salaire_max,
    )


def get_employee_row(employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """Ligne employé brute (salaire, etc.) sans enrichissement pour opérations RH."""
    return _employee_repository.get_by_id(employee_id, company_id)


def get_salary_history_rows(
    employee_id: str,
    company_id: str,
) -> List[Dict[str, Any]]:
    """Historique des salaires (table salary_history)."""
    return _employee_repository.get_salary_history(employee_id, company_id)
