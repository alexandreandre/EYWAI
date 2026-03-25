"""
Cas d'usage en lecture du module employees.

Délègue au repository, storage provider et queries infrastructure.
Comportement identique au router legacy. Aucun accès DB direct.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.employees.application.service import (
    enrich_employee_with_annual_review,
    enrich_employee_with_residence_permit_status,
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
)
from app.modules.employees.infrastructure.repository import EmployeeRepository

# Repository partagé (pas d'injection pour l'instant, comportement identique)
_employee_repository = EmployeeRepository()


def get_employees(company_id: str) -> List[Dict[str, Any]]:
    """
    Liste des employés de l'entreprise (enrichis titre de séjour).
    Comportement identique à get_employees (router legacy).
    """
    rows = _employee_repository.get_by_company(company_id)
    return [enrich_employee_with_residence_permit_status(row) for row in rows]


def get_employee_by_id(employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """
    Détail d'un employé (enrichi titre de séjour + entretien annuel).
    Comportement identique à get_employee_details (router legacy).
    """
    data = _employee_repository.get_by_id(employee_id, company_id)
    if not data:
        return None
    data = enrich_employee_with_residence_permit_status(data)
    data = enrich_employee_with_annual_review(data)
    return data


def get_my_contract_url(employee_id: str) -> Optional[str]:
    """
    URL signée de téléchargement du contrat (espace employé).
    Comportement identique à get_my_contract (router legacy).
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None
    storage = get_storage_provider()
    list_response = storage.list_files("contracts", f"{company_id}/{employee_id}")
    if not any(f.get("name") == "contrat.pdf" for f in list_response):
        return None
    return storage.create_signed_url(
        "contracts",
        f"{company_id}/{employee_id}/contrat.pdf",
        expiry_seconds=3600,
        download=True,
    )


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
    Comportement identique à get_employee_credentials_pdf_url (router legacy).
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None
    storage = get_storage_provider()
    list_response = storage.list_files("creation_compte", f"{company_id}/{employee_id}")
    if not any(f.get("name") == "creation_compte.pdf" for f in list_response):
        return None
    return storage.create_signed_url(
        "creation_compte",
        f"{company_id}/{employee_id}/creation_compte.pdf",
        expiry_seconds=3600,
        download=True,
    )


def get_identity_document_url(employee_id: str) -> Optional[str]:
    """
    URL signée de la pièce d'identité (espace RH).
    Comportement identique à get_employee_identity_document_url (router legacy).
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None
    storage = get_storage_provider()
    list_response = storage.list_files("piece_identite", f"{company_id}/{employee_id}")
    for ext in [".pdf", ".jpg", ".jpeg", ".png"]:
        name = f"piece_identite{ext}"
        if any(f.get("name") == name for f in list_response):
            return storage.create_signed_url(
                "piece_identite",
                f"{company_id}/{employee_id}/{name}",
                expiry_seconds=3600,
                download=True,
            )
    return None


def get_contract_url(employee_id: str) -> Optional[str]:
    """
    URL signée du contrat PDF (espace RH).
    Comportement identique à get_employee_contract_url (router legacy).
    """
    company_id = get_employee_company_id(employee_id)
    if not company_id:
        return None
    storage = get_storage_provider()
    list_response = storage.list_files("contracts", f"{company_id}/{employee_id}")
    if not any(f.get("name") == "contrat.pdf" for f in list_response):
        return None
    return storage.create_signed_url(
        "contracts",
        f"{company_id}/{employee_id}/contrat.pdf",
        expiry_seconds=3600,
        download=True,
    )


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
