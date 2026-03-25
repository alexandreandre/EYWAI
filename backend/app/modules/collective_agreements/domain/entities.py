"""
Entités du domaine collective_agreements.

Structure alignée sur les tables collective_agreements_catalog, company_collective_agreements,
collective_agreement_texts (cache chat). Migration : logique métier à déplacer ici.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class CollectiveAgreementCatalogEntity:
    """Convention du catalogue (table collective_agreements_catalog)."""

    id: str
    name: str
    idcc: str
    description: Optional[str]
    sector: Optional[str]
    effective_date: Optional[date]
    is_active: bool
    rules_pdf_path: Optional[str]
    rules_pdf_filename: Optional[str]
    created_at: datetime
    updated_at: datetime
    rules_pdf_url: Optional[str] = None  # Rempli côté infra (URL signée)


@dataclass
class CompanyAssignmentEntity:
    """Assignation entreprise <-> convention (table company_collective_agreements)."""

    id: str
    company_id: str
    collective_agreement_id: str
    assigned_at: datetime
    assigned_by: Optional[str]
    agreement_details: Optional[CollectiveAgreementCatalogEntity] = None  # JOIN optionnel


@dataclass
class CachedAgreementTextEntity:
    """Cache du texte extrait d'un PDF (table collective_agreement_texts, pour le chat)."""

    agreement_id: str
    full_text: str
    character_count: int
    pdf_hash: Optional[str] = None
