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
