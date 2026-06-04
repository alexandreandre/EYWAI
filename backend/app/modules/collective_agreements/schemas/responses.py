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


# --- Règles paie (extraction IA) ---


class KaliImportRulesSummary(BaseModel):
    success: bool
    error: Optional[str] = None
    confidence: Optional[str] = None


class KaliImportResponse(BaseModel):
    success: bool
    idcc: str
    agreement_id: Optional[str] = None
    title: Optional[str] = None
    legifrance_url: Optional[str] = None
    character_count: int = 0
    created: bool = False
    error: Optional[str] = None
    rules: Optional[KaliImportRulesSummary] = None


class KaliImportBatchResponse(BaseModel):
    results: List[KaliImportResponse]
    total: int
    succeeded: int
    failed: int


class ExtractRulesResponse(BaseModel):
    """Réponse POST extract-rules."""

    success: bool
    idcc: str
    agreement_id: Optional[str] = None
    rules: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    tokens_used: int = 0
    confidence: Optional[str] = None
    log_id: Optional[str] = None


class ExtractRulesBatchResponse(BaseModel):
    """Réponse POST extract-rules/batch."""

    results: List[ExtractRulesResponse]
    total: int
    succeeded: int
    failed: int


class RulesStatusResponse(BaseModel):
    """Réponse GET rules-status."""

    idcc: str
    agreement_id: str
    has_rules: bool
    rules: Optional[dict[str, Any]] = None
    source_text_hash: Optional[str] = None
    extracted_at: Optional[str] = None
    extraction_model: Optional[str] = None
    latest_log_status: Optional[str] = None
    latest_log_error: Optional[str] = None
    confidence: Optional[str] = None
    text_source: Optional[str] = None


class RollbackRulesResponse(BaseModel):
    """Réponse POST rules/rollback."""

    success: bool
    rules: Optional[dict[str, Any]] = None
    message: Optional[str] = None
