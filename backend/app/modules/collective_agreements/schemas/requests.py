"""
Schémas requêtes API pour collective_agreements.

Structure alignée sur le legacy (api/routers/collective_agreements*.py, schemas/collective_agreement.py).
Migration : remplacer les imports legacy par ceux-ci.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# --- Catalogue (super admin) ---


class CollectiveAgreementCatalogCreate(BaseModel):
    """Création d'une entrée catalogue (nom, idcc, pdf, etc.)."""

    name: str
    idcc: str
    description: Optional[str] = None
    sector: Optional[str] = None
    effective_date: Optional[date] = None
    is_active: bool = True
    rules_pdf_path: Optional[str] = None
    rules_pdf_filename: Optional[str] = None


class CollectiveAgreementCatalogUpdate(BaseModel):
    """Mise à jour partielle d'une entrée catalogue."""

    name: Optional[str] = None
    idcc: Optional[str] = None
    description: Optional[str] = None
    sector: Optional[str] = None
    effective_date: Optional[date] = None
    rules_pdf_path: Optional[str] = None
    rules_pdf_filename: Optional[str] = None
    is_active: Optional[bool] = None


# --- Assignation (RH) ---


class CompanyCollectiveAgreementCreate(BaseModel):
    """Création d'une liaison entreprise <-> convention (legacy / usage interne)."""

    company_id: str
    collective_agreement_id: str


class AssignAgreementBody(BaseModel):
    """Corps POST /assign : id de la convention à assigner à l'entreprise active."""

    collective_agreement_id: str = Field(
        ..., description="ID de la convention collective"
    )


# --- Upload URL (super admin) ---


class GetUploadUrlBody(BaseModel):
    """Corps POST /catalog/upload-url : nom de fichier pour générer l'URL signée."""

    filename: str = Field(..., description="Nom du fichier (ex. document.pdf)")


# --- Chat (question sur une convention) ---


class QuestionRequest(BaseModel):
    """Corps POST /ask (collective-agreements-chat) : question sur une convention."""

    agreement_id: str = Field(..., description="ID de la convention collective")
    question: str = Field(..., description="Question posée à l'assistant")


# --- Extraction règles paie (super admin) ---


class KaliImportRequest(BaseModel):
    """Corps POST import Légifrance."""

    idcc: str = Field(..., description="Numéro IDCC (ex. 1486)")
    extract_rules: bool = Field(
        True, description="Lancer l'extraction IA des règles paie après import"
    )
    sector: Optional[str] = None


class KaliImportBatchRequest(BaseModel):
    """Corps POST import batch Légifrance."""

    idcc_list: Optional[list[str]] = None
    priority_only: bool = False
    extract_rules: bool = True


class KaliSyncCatalogRequest(BaseModel):
    """Corps POST sync catalogue Légifrance (toutes les CC actives)."""

    extract_rules: bool = Field(
        True,
        description="Extraire les règles paie uniquement si le texte a changé",
    )


class KaliImportCancelRequest(BaseModel):
    """Corps POST annulation import Légifrance en cours."""

    idcc: Optional[str] = Field(
        None, description="Numéro IDCC à interrompre (import unitaire)"
    )
    catalog_sync: bool = Field(
        False, description="Interrompre la sync de tout le catalogue en cours"
    )


class ExtractRulesBatchRequest(BaseModel):
    """Corps POST batch extract-rules."""

    idcc_list: Optional[list[str]] = Field(
        None, description="Liste d'IDCC à traiter"
    )
    all_catalog: bool = Field(False, description="Traiter tout le catalogue actif")
    priority_only: bool = Field(
        False, description="Traiter uniquement les IDCC prioritaires (lot 1)"
    )
    dry_run: bool = Field(False, description="Simuler sans appel IA")


class CcTrainingRecommendationUpdate(BaseModel):
    """Corps PATCH training-recommendations/{id}."""

    title: Optional[str] = None
    is_active: Optional[bool] = None
    obligation_level: Optional[str] = None
    pedagogical_objective: Optional[str] = None
    legal_reference: Optional[str] = None
