"""
Schémas réponses API pour collective_agreements.

Migrés depuis schemas/collective_agreement.py. Comportement identique.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


# --- Catalogue (conventions collectives françaises) ---


class CollectiveAgreementCatalogBase(BaseModel):
    """Champs de base d'une convention du catalogue."""

    name: str
    idcc: str
    description: Optional[str] = None
    sector: Optional[str] = None
    effective_date: Optional[date] = None
    is_active: bool = True


class CollectiveAgreementCatalog(CollectiveAgreementCatalogBase):
    """Convention du catalogue (lecture, avec URL signée PDF si présent)."""

    id: str
    created_at: datetime
    updated_at: datetime
    rules_pdf_path: Optional[str] = None
    rules_pdf_filename: Optional[str] = None
    rules_pdf_url: Optional[str] = None  # URL signée générée dynamiquement

    model_config = ConfigDict(from_attributes=True)


# --- Liaison (assignation entreprise <-> convention) ---


class CompanyCollectiveAgreement(BaseModel):
    """Assignation entreprise <-> convention (sans détails)."""

    id: str
    company_id: str
    collective_agreement_id: str
    assigned_at: datetime
    assigned_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CompanyCollectiveAgreementWithDetails(CompanyCollectiveAgreement):
    """Liaison avec les détails complets de la convention."""

    agreement_details: CollectiveAgreementCatalog

    model_config = ConfigDict(from_attributes=True)


# --- Chat ---


class QuestionResponse(BaseModel):
    """Réponse POST /ask : réponse du LLM + nom de la convention."""

    answer: str
    agreement_name: str


# --- Divers (upload URL, assign, all-assignments) ---


class UploadUrlResponse(BaseModel):
    """Réponse POST /catalog/upload-url."""

    path: str
    signedURL: str


class AssignResponse(BaseModel):
    """Réponse POST /assign."""

    message: str
    assignment: dict[str, Any]


class AllAssignmentsCompanyItem(BaseModel):
    """Un item de la liste GET /all-assignments (super admin)."""

    id: str
    company_name: str
    assigned_agreements: List[dict[str, Any]]
